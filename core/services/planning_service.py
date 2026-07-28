"""Kural tabanlı günlük plan üretimi (sirkadiyen ritim yaklaşımı, OpenAI'sız).

`gerekce_uret` parametresi bilinçli olarak enjekte edilebilir bırakıldı:
gelecekte gerçek bir OpenAI tabanlı `ai_advisor.py` bu tek fonksiyonu
değiştirerek devreye girebilir, geri kalan yerleştirme mantığına dokunmadan.
"""

import logging
from datetime import date, time
from typing import Callable

from core.database import SessionLocal
from core.models import PlanKaydi, Task

logger = logging.getLogger(__name__)

GUN_BASLANGIC = time(6, 0)
GUN_BITIS = time(23, 0)
OGLEDEN_SONRA_BITIS = time(18, 0)


def _dk(t: time) -> int:
    return t.hour * 60 + t.minute


def _saat_str(dk: int) -> str:
    dk %= 24 * 60
    return f"{dk // 60:02d}:{dk % 60:02d}"


def _araligi_cikar(bos: list[tuple[int, int]], cikarilacak: tuple[int, int]) -> list[tuple[int, int]]:
    """`bos` aralık listesinden `cikarilacak` aralığını keser."""
    c_baslangic, c_bitis = cikarilacak
    sonuc = []
    for b_baslangic, b_bitis in bos:
        if c_bitis <= b_baslangic or c_baslangic >= b_bitis:
            sonuc.append((b_baslangic, b_bitis))
            continue
        if c_baslangic > b_baslangic:
            sonuc.append((b_baslangic, c_baslangic))
        if c_bitis < b_bitis:
            sonuc.append((c_bitis, b_bitis))
    return sonuc


def _sarmali_araligi_gune_ekle(bloklar: list[tuple[int, int]], baslangic: time, bitis: time) -> None:
    """Gece yarısını saran (örn. 23:00-07:00) bir aralığı gün sınırları içine kırpıp ekler."""
    gun_baslangic, gun_bitis = _dk(GUN_BASLANGIC), _dk(GUN_BITIS)
    b, e = _dk(baslangic), _dk(bitis)
    if b == e:
        return
    if b < e:
        parcalar = [(b, e)]
    else:
        parcalar = [(b, 24 * 60), (0, e)]
    for p_baslangic, p_bitis in parcalar:
        kirpilmis_baslangic = max(p_baslangic, gun_baslangic)
        kirpilmis_bitis = min(p_bitis, gun_bitis)
        if kirpilmis_baslangic < kirpilmis_bitis:
            bloklar.append((kirpilmis_baslangic, kirpilmis_bitis))


def _bos_araliklar(profil, uygun_olmayan_bloklar: list[dict]) -> list[tuple[int, int]]:
    """Gün sınırları içinde, meşgul bloklar ve uyku penceresi çıkarılmış boş aralıklar."""
    bos = [(_dk(GUN_BASLANGIC), _dk(GUN_BITIS))]

    mesgul: list[tuple[int, int]] = []
    _sarmali_araligi_gune_ekle(mesgul, profil.uyku_baslangic, profil.uyku_bitis)
    for blok in uygun_olmayan_bloklar:
        _sarmali_araligi_gune_ekle(mesgul, blok["start"], blok["end"])

    for aralik in mesgul:
        bos = _araligi_cikar(bos, aralik)
    return sorted(bos)


def _yerlestir(bos: list[tuple[int, int]], sure: int, tercih: tuple[int, int]) -> tuple[int, list[tuple[int, int]]] | None:
    """Süreyi önce tercih edilen pencerede, olmazsa ilk uyan boş aralıkta yerleştirir."""
    t_baslangic, t_bitis = tercih
    for b_baslangic, b_bitis in bos:
        aday_baslangic = max(b_baslangic, t_baslangic)
        aday_bitis = min(b_bitis, t_bitis)
        if aday_bitis - aday_baslangic >= sure:
            yeni_bos = _araligi_cikar(bos, (aday_baslangic, aday_baslangic + sure))
            return aday_baslangic, sorted(yeni_bos)

    for b_baslangic, b_bitis in bos:
        if b_bitis - b_baslangic >= sure:
            yeni_bos = _araligi_cikar(bos, (b_baslangic, b_baslangic + sure))
            return b_baslangic, sorted(yeni_bos)

    return None


def _tercih_penceresi(oncelik: int, profil) -> tuple[int, int]:
    if oncelik == 3:
        return _dk(profil.verimli_baslangic), _dk(profil.verimli_bitis)
    if oncelik == 2:
        return _dk(profil.verimli_bitis), _dk(OGLEDEN_SONRA_BITIS)
    return _dk(OGLEDEN_SONRA_BITIS), _dk(GUN_BITIS)


def _varsayilan_gerekce_uret(task: Task, baslangic_dk: int, tercih_penceresinde: bool, profil) -> str:
    if task.priority == 3:
        if tercih_penceresinde:
            return "Sabah saatleri en verimli zamanın. Kritik görevi buraya yerleştirdim."
        return "En verimli pencerende yeterli boşluk yoktu, kritik görevi en uygun boş zamana yerleştirdim."
    if task.priority == 2:
        return "Öğle sonrası hafif-orta görevler daha uygun. Odak biraz azalıyor."
    return "Düşük zorluk görevi güne son. Hızlı kazanç sağlar."


def _genel_tavsiye_uret(kritik_tercih_penceresinde: int, toplam_kritik: int) -> str:
    if toplam_kritik == 0:
        return (
            "Bugün için kritik öncelikli görev yok. Yine de sabah saatlerini görece "
            "zor işler için ayırman verimliliğini artırabilir."
        )
    oran = kritik_tercih_penceresinde / toplam_kritik
    if oran == 1:
        yuzde = 35
        return (
            "Geçmiş verine göre en verimli olduğun saatler günün en üretken zamanı. "
            "Kritik görevlerin tamamını buraya yerleştirdim. "
            f"**Sabah rutinine sadık kalırsan verimliliğin %{yuzde} artacak.**"
        )
    yuzde = 15
    return (
        "Kritik görevlerin bir kısmı en verimli pencerene sığmadı. "
        f"**Uygun olmayan saatleri azaltırsan verimliliğin %{yuzde} artabilir.**"
    )


def plan_olustur(
    gun: date,
    gorevler: list[Task],
    uygun_olmayan_bloklar: list[dict],
    profil,
    gerekce_uret: Callable = _varsayilan_gerekce_uret,
) -> PlanKaydi:
    """Verilen gün için kural tabanlı bir plan üretir, yeni bir PlanKaydi olarak kaydeder."""
    bos = _bos_araliklar(profil, uygun_olmayan_bloklar)
    toplam_bos_baslangic = sum(b - a for a, b in bos)

    sirali_gorevler = sorted(gorevler, key=lambda t: (-t.priority, t.duration_minutes))

    dilimler = []
    kritik_tercih_penceresinde = 0
    toplam_kritik = sum(1 for t in sirali_gorevler if t.priority == 3)

    for task in sirali_gorevler:
        tercih = _tercih_penceresi(task.priority, profil)
        sonuc = _yerlestir(bos, task.duration_minutes, tercih)
        if sonuc is None:
            continue
        baslangic_dk, bos = sonuc
        bitis_dk = baslangic_dk + task.duration_minutes
        tercih_penceresinde = tercih[0] <= baslangic_dk and bitis_dk <= tercih[1]
        if task.priority == 3 and tercih_penceresinde:
            kritik_tercih_penceresinde += 1

        gerekce = gerekce_uret(task, baslangic_dk, tercih_penceresinde, profil)
        dilimler.append({
            "task_id": task.id,
            "title": task.title,
            "start": _saat_str(baslangic_dk),
            "end": _saat_str(bitis_dk),
            "duration_minutes": task.duration_minutes,
            "gerekce": gerekce,
        })

    dilimler.sort(key=lambda d: d["start"])

    toplam_is_dakika = sum(d["duration_minutes"] for d in dilimler)
    bos_zaman_dakika = toplam_bos_baslangic - toplam_is_dakika
    genel_tavsiye = _genel_tavsiye_uret(kritik_tercih_penceresinde, toplam_kritik)

    with SessionLocal() as session:
        kayit = PlanKaydi(
            gun=gun,
            dilimler=dilimler,
            toplam_is_dakika=toplam_is_dakika,
            bos_zaman_dakika=bos_zaman_dakika,
            genel_tavsiye=genel_tavsiye,
        )
        session.add(kayit)
        session.commit()
        session.refresh(kayit)

    yerlesemeyen = len(sirali_gorevler) - len(dilimler)
    logger.info(
        "%s günü için plan oluşturuldu: %d/%d görev yerleştirildi (%d yerleşemedi)",
        gun, len(dilimler), len(sirali_gorevler), yerlesemeyen,
    )
    return kayit


def son_plan(gun: date) -> PlanKaydi | None:
    """O güne ait en son oluşturulan planı döner, yoksa None."""
    with SessionLocal() as session:
        return (
            session.query(PlanKaydi)
            .filter(PlanKaydi.gun == gun)
            .order_by(PlanKaydi.created_at.desc())
            .first()
        )
