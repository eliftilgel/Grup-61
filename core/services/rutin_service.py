"""Rutin (tekrarlayan görev şablonu) CRUD'u ve haftalık materyalize mantığı.

Bir rutin, `gunler`de belirtilen haftanın günlerinde `saat`te sabit bir görev
olarak materyalize edilir (bkz. `haftalik_rutinleri_uret`). Materyalize edilen
her occurrence bağımsız bir `Task` (tur="gorev") satırıdır — kullanıcı normal
görev CRUD'uyla (task_service) düzenleyebilir/tamamlayabilir/silebilir.
"""

from datetime import date, time, timedelta

from core.database import SessionLocal
from core.models import Rutin, Task

GECERLI_GUNLER = range(7)
RUTIN_ANALIZ_PENCERESI = 8
ROUTIN_ERTELEME_ORAN_ESIGI = 0.5
ROUTIN_MIN_ORNEK = 3


def _rutin_bilgisini_dogrula(baslik: str, gunler: list[int], sure_dakika: int, oncelik: int) -> None:
    if not baslik.strip():
        raise ValueError("Rutin başlığı boş olamaz")
    if not gunler:
        raise ValueError("En az bir gün seçmelisin")
    if any(g not in GECERLI_GUNLER for g in gunler):
        raise ValueError("Geçersiz gün değeri")
    if sure_dakika <= 0:
        raise ValueError("Süre 0'dan büyük olmalı")
    if oncelik not in (1, 2, 3):
        raise ValueError("Öncelik 1, 2 veya 3 olmalı")


def create_rutin(
    user_id: int, baslik: str, gunler: list[int], saat: time, sure_dakika: int = 30, oncelik: int = 2
) -> Rutin:
    """Yeni rutin şablonunu veritabanına kaydeder ve döner."""
    _rutin_bilgisini_dogrula(baslik, gunler, sure_dakika, oncelik)
    with SessionLocal() as session:
        rutin = Rutin(
            user_id=user_id,
            baslik=baslik.strip(),
            gunler=sorted(set(gunler)),
            saat=saat,
            sure_dakika=sure_dakika,
            oncelik=oncelik,
        )
        session.add(rutin)
        session.commit()
        session.refresh(rutin)
        return rutin


def list_rutinler(user_id: int) -> list[Rutin]:
    """Kullanıcının rutinlerini başlığa göre listeler."""
    with SessionLocal() as session:
        return list(session.query(Rutin).filter(Rutin.user_id == user_id).order_by(Rutin.baslik))


def _sahiplenilen_rutini_getir(session, user_id: int, rutin_id: int) -> Rutin:
    rutin = session.query(Rutin).filter(Rutin.id == rutin_id, Rutin.user_id == user_id).one_or_none()
    if rutin is None:
        raise ValueError(f"{rutin_id} numaralı rutin bulunamadı.")
    return rutin


def update_rutin(
    user_id: int,
    rutin_id: int,
    baslik: str,
    gunler: list[int],
    saat: time,
    sure_dakika: int,
    oncelik: int,
    aktif: bool = True,
) -> Rutin:
    """Rutinin alanlarını topluca günceller."""
    _rutin_bilgisini_dogrula(baslik, gunler, sure_dakika, oncelik)
    with SessionLocal() as session:
        rutin = _sahiplenilen_rutini_getir(session, user_id, rutin_id)
        rutin.baslik = baslik.strip()
        rutin.gunler = sorted(set(gunler))
        rutin.saat = saat
        rutin.sure_dakika = sure_dakika
        rutin.oncelik = oncelik
        rutin.aktif = aktif
        session.commit()
        session.refresh(rutin)
        return rutin


def delete_rutin(user_id: int, rutin_id: int) -> None:
    """Rutini kalıcı olarak siler (materyalize edilmiş görevler rutin_id=NULL olarak kalır)."""
    with SessionLocal() as session:
        rutin = _sahiplenilen_rutini_getir(session, user_id, rutin_id)
        session.delete(rutin)
        session.commit()


def haftalik_rutinleri_uret(user_id: int, hafta_icindeki_gun: date) -> int:
    """`hafta_icindeki_gun`u içeren Pazartesi-Pazar haftasının her günü için, o güne
    denk gelen aktif rutinlerden henüz o gün için materyalize edilmemiş olanları
    Task (tur="gorev") olarak oluşturur. Aynı rutin+gün için tekrar çağrılırsa
    ikinci kez üretmez (idempotent). Üretilen görev sayısını döner.
    """
    hafta_baslangic = hafta_icindeki_gun - timedelta(days=hafta_icindeki_gun.weekday())
    uretilen = 0
    with SessionLocal() as session:
        rutinler = session.query(Rutin).filter(Rutin.user_id == user_id, Rutin.aktif.is_(True)).all()
        if not rutinler:
            return 0
        for gun_offset in range(7):
            gun = hafta_baslangic + timedelta(days=gun_offset)
            haftanin_gunu = gun.weekday()
            for rutin in rutinler:
                if haftanin_gunu not in rutin.gunler:
                    continue
                zaten_var = (
                    session.query(Task)
                    .filter(Task.user_id == user_id, Task.rutin_id == rutin.id, Task.due_date == gun)
                    .one_or_none()
                )
                if zaten_var is not None:
                    continue
                session.add(Task(
                    user_id=user_id,
                    title=rutin.baslik,
                    priority=rutin.oncelik,
                    duration_minutes=rutin.sure_dakika,
                    due_date=gun,
                    sabit_saat=rutin.saat,
                    rutin_id=rutin.id,
                    tur="gorev",
                ))
                uretilen += 1
        session.commit()
    return uretilen


def _rutin_erteleme_onerisi_uret(session, user_id: int, rutin: Rutin) -> str | None:
    gorevler = (
        session.query(Task)
        .filter(Task.user_id == user_id, Task.rutin_id == rutin.id)
        .order_by(Task.due_date.desc())
        .limit(RUTIN_ANALIZ_PENCERESI)
        .all()
    )
    if len(gorevler) < ROUTIN_MIN_ORNEK:
        return None
    ertelenen_sayisi = sum(1 for g in gorevler if g.postponement_count > 0)
    if ertelenen_sayisi / len(gorevler) >= ROUTIN_ERTELEME_ORAN_ESIGI:
        return (
            f"'{rutin.baslik}' rutini sık ertelendi ({ertelenen_sayisi}/{len(gorevler)}) — "
            "farklı bir gün veya saat denemeyi düşün."
        )
    return None


def rutin_erteleme_onerisi(user_id: int, rutin_id: int) -> str | None:
    """Tek bir rutin için, son materyalize görevlerinin ertelenme oranı eşiği
    aşıyorsa öneri metnini döner; aksi halde None (metin, otomatik değişiklik yapmaz)."""
    with SessionLocal() as session:
        rutin = _sahiplenilen_rutini_getir(session, user_id, rutin_id)
        return _rutin_erteleme_onerisi_uret(session, user_id, rutin)


def rutin_erteleme_onerilerini_uret(user_id: int) -> list[str]:
    """Her aktif rutin için son materyalize görevlerini toplar; ertelenme oranı
    eşiği aşıyorsa 'farklı gün/saat dene' önerisi üretir (metin, otomatik değişiklik yapmaz).
    """
    with SessionLocal() as session:
        rutinler = session.query(Rutin).filter(Rutin.user_id == user_id, Rutin.aktif.is_(True)).all()
        oneriler = [_rutin_erteleme_onerisi_uret(session, user_id, r) for r in rutinler]
        return [o for o in oneriler if o is not None]
