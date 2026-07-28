"""Demo amaçlı gerçekçi veri üretir: 4 kullanıcı, her biri için son 30 gün.

Kullanım:
    python scripts/seed_demo_data.py

Gerçek `planning_service.plan_olustur()` ve `task_service.update_task()`
akışlarını kullanır (sahte JSON üretmez) — böylece AI Planı, Rapor ve
Admin ekranları gerçek uygulama mantığıyla dolu görünür. Zaten demo
kullanıcılar varsa script uyarıp hiçbir şey yapmadan çıkar.
"""

import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal  # noqa: E402
from core.models import Task, User  # noqa: E402
from core.services import planning_service, profil_service, user_service  # noqa: E402
from core.services.task_service import update_task  # noqa: E402

random.seed(42)

GOREV_HAVUZU = [
    ("Rapor yaz", 3, 90),
    ("Toplantıya katıl", 2, 60),
    ("Spor yap", 1, 45),
    ("Fatura öde", 2, 15),
    ("Sunum hazırla", 3, 120),
    ("Email cevapla", 2, 30),
    ("Kitap oku", 1, 30),
    ("Market alışverişi", 1, 45),
    ("Kod incele", 3, 60),
    ("Müşteri görüşmesi", 3, 45),
    ("Temizlik yap", 1, 60),
    ("Proje planla", 2, 90),
]

DEMO_KULLANICILAR = [
    {
        "username": "ayse_yilmaz", "password": "demo1234", "ad_soyad": "Ayşe Yılmaz",
        "verimli": (time(7, 0), time(13, 0)), "uyku": (time(23, 0), time(7, 0)), "hedef": 5,
    },
    {
        "username": "mehmet_kaya", "password": "demo1234", "ad_soyad": "Mehmet Kaya",
        "verimli": (time(9, 0), time(15, 0)), "uyku": (time(0, 0), time(8, 0)), "hedef": 4,
    },
    {
        "username": "elif_demir", "password": "demo1234", "ad_soyad": "Elif Demir",
        "verimli": (time(6, 0), time(11, 0)), "uyku": (time(22, 0), time(6, 0)), "hedef": 6,
    },
    {
        "username": "can_ozturk", "password": "demo1234", "ad_soyad": "Can Öztürk",
        "verimli": (time(10, 0), time(16, 0)), "uyku": (time(1, 0), time(9, 0)), "hedef": 3,
    },
]

GUN_SAYISI = 30


def _demo_kullanicilar_var_mi() -> bool:
    kullanici_adlari = [k["username"] for k in DEMO_KULLANICILAR]
    with SessionLocal() as session:
        return session.query(User).filter(User.username.in_(kullanici_adlari)).first() is not None


def _gunluk_gorevler_olustur(user_id: int, gun: date) -> list[Task]:
    gorevler = []
    for _ in range(random.randint(2, 5)):
        baslik, oncelik, sure_taban = random.choice(GOREV_HAVUZU)
        sure = max(15, sure_taban + random.choice([-15, 0, 15]))
        with SessionLocal() as session:
            task = Task(
                user_id=user_id,
                title=baslik,
                priority=oncelik,
                due_date=gun,
                duration_minutes=sure,
                created_at=datetime.combine(gun, time(8, 0), tzinfo=timezone.utc),
            )
            session.add(task)
            session.commit()
            session.refresh(task)
        gorevler.append(task)
    return gorevler


def _bazi_gorevleri_tamamla(gorevler: list[Task], gun: date, olasilik: float = 0.75) -> None:
    for task in gorevler:
        if random.random() < olasilik:
            with SessionLocal() as session:
                t = session.get(Task, task.id)
                t.done = True
                t.completed_at = datetime.combine(gun, time(18, 0), tzinfo=timezone.utc)
                session.commit()


def _kullanici_icin_veri_uret(bilgi: dict) -> None:
    kullanici = user_service.create_user(bilgi["username"], bilgi["password"])
    profil_service.save(
        kullanici.id, bilgi["ad_soyad"], f"{bilgi['username']}@planla.demo",
        bilgi["verimli"][0], bilgi["verimli"][1], bilgi["uyku"][0], bilgi["uyku"][1], bilgi["hedef"],
    )
    profil = profil_service.get_or_create(kullanici.id)

    bugun = date.today()
    for gun_index in range(GUN_SAYISI - 1, -1, -1):
        gun = bugun - timedelta(days=gun_index)
        gunun_gorevleri = _gunluk_gorevler_olustur(kullanici.id, gun)

        # Gün için görevler henüz tamamlanmamışken plan oluşturulur (gerçek kullanım sırasıyla aynı).
        if gunun_gorevleri and random.random() < 0.8:
            planning_service.plan_olustur(kullanici.id, gun, gunun_gorevleri, [], profil)

        if gun < bugun:
            _bazi_gorevleri_tamamla(gunun_gorevleri, gun)

    # Birkaç eski, hâlâ tamamlanmamış görevi bugüne "ertele" — gerçek update_task akışı,
    # postponement_count'u ve Rapor'daki "En Çok Ertelenen Görevler" listesini doldurur.
    with SessionLocal() as session:
        ertelenebilecekler = (
            session.query(Task)
            .filter(Task.user_id == kullanici.id, Task.done.is_(False), Task.due_date < bugun)
            .limit(3)
            .all()
        )
        ertelenebilecekler = [(t.id, t.title, t.description, t.priority, t.duration_minutes) for t in ertelenebilecekler]

    for task_id, title, description, priority, duration_minutes in ertelenebilecekler:
        update_task(kullanici.id, task_id, title, description, priority,
                     due_date=bugun, duration_minutes=duration_minutes)

    print(f"  [OK] {kullanici.username} ({bilgi['ad_soyad']}) - {GUN_SAYISI} gunluk veri olusturuldu")


def ana() -> None:
    if _demo_kullanicilar_var_mi():
        print("Demo kullanıcılar zaten mevcut — tekrar eklenmeyi önlemek için script durduruldu.")
        print("Zaten var olan demo hesaplarıyla admin panelinden devam edebilirsin.")
        return

    print(f"{len(DEMO_KULLANICILAR)} demo kullanıcı için {GUN_SAYISI} günlük veri üretiliyor...")
    for bilgi in DEMO_KULLANICILAR:
        _kullanici_icin_veri_uret(bilgi)
    print("Tamamlandi. Admin hesabiyla giris yapip Admin sekmesinden goruntuleyebilirsin.")


if __name__ == "__main__":
    ana()
