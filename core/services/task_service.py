"""Görev İşlemleri - arayüzden bağımsız iş mantığı."""

from core.database import SessionLocal
from core.models import Task
from datetime import date, datetime, timezone

TESLIM_TIPLERI = ("esnek", "kesin")


def _teslim_bilgisini_dogrula(
    teslim_tipi: str, due_date: date | None, kesin_bitis: datetime | None
) -> tuple[date | None, datetime | None]:
    """teslim_tipi'ni doğrular; 'kesin' için due_date'i kesin_bitis'ten türetir."""
    if teslim_tipi not in TESLIM_TIPLERI:
        raise ValueError("Teslim tipi 'esnek' veya 'kesin' olmalı")
    if teslim_tipi == "kesin":
        if kesin_bitis is None:
            raise ValueError("Kesin teslimli görev için bitiş tarihi/saati zorunlu")
        return kesin_bitis.date(), kesin_bitis
    return due_date, None


def _en_erken_baslangici_dogrula(due_date: date | None, en_erken_baslangic: date | None) -> None:
    if due_date is not None and en_erken_baslangic is not None and due_date < en_erken_baslangic:
        raise ValueError("Son tarih, en erken başlangıç tarihinden önce olamaz")


def create_task(
    user_id: int,
    title: str,
    description: str = "",
    priority: int = 1,
    due_date: date | None = None,
    duration_minutes: int = 30,
    konum: str = "",
    link: str = "",
    teslim_tipi: str = "esnek",
    kesin_bitis: datetime | None = None,
    en_erken_baslangic: date | None = None,
) -> Task:
    """Yeni görevi veritabanına kaydeder ve döner."""
    if not title.strip():
        raise ValueError("Görev başlığı boş olamaz")
    if priority not in (1, 2, 3):
        raise ValueError("Öncelik 1, 2 veya 3 olmalı")
    if duration_minutes <= 0:
        raise ValueError("Süre 0'dan büyük olmalı")
    due_date, kesin_bitis = _teslim_bilgisini_dogrula(teslim_tipi, due_date, kesin_bitis)
    _en_erken_baslangici_dogrula(due_date, en_erken_baslangic)

    with SessionLocal() as session:
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            duration_minutes=duration_minutes,
            konum=konum,
            link=link,
            teslim_tipi=teslim_tipi,
            kesin_bitis=kesin_bitis,
            en_erken_baslangic=en_erken_baslangic,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def list_tasks(
    user_id: int,
    include_done: bool = True,
    only_done: bool = False,
    due_date: date | None = None,
    tur: str = "gorev",
) -> list[Task]:
    """Kullanıcının kayıtlarını öncelik sırasına göre listeler.

    `tur` varsayılan olarak "gorev" — etkinlik satırları (`tur="etkinlik"`)
    çağıran açıkça istemedikçe görev listelerine karışmaz.
    """
    with SessionLocal() as session:
        query = (
            session.query(Task)
            .filter(Task.user_id == user_id, Task.tur == tur)
            .order_by(Task.priority.desc(), Task.created_at.desc())
        )
        if only_done:
            query = query.filter(Task.done.is_(True))
        elif not include_done:
            query = query.filter(Task.done.is_(False))
        if due_date is not None:
            query = query.filter(Task.due_date == due_date)
        return list(query)


def gecikmis_gorevleri_listele(user_id: int, referans_gun: date) -> list[Task]:
    """referans_gun'dan önce vadesi geçmiş, henüz tamamlanmamış görevleri döner."""
    with SessionLocal() as session:
        return list(
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.tur == "gorev",
                Task.due_date < referans_gun,
                Task.done.is_(False),
            )
            .order_by(Task.priority.desc(), Task.due_date.asc())
        )


def _sahiplenilen_gorevi_getir(session, user_id: int, task_id: int) -> Task:
    task = (
        session.query(Task)
        .filter(Task.id == task_id, Task.user_id == user_id, Task.tur == "gorev")
        .one_or_none()
    )
    if task is None:
        raise ValueError(f"{task_id} numaralı görev bulunamadı.")
    return task


def complete_task(user_id: int, task_id: int) -> Task:
    """Görevi tamamlandı olarak işaretler."""
    with SessionLocal() as session:
        task = _sahiplenilen_gorevi_getir(session, user_id, task_id)
        task.done = True
        task.completed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(task)
        return task

def update_task(
    user_id: int,
    task_id: int,
    title: str,
    description: str,
    priority: int,
    due_date: date | None = None,
    duration_minutes: int = 30,
    konum: str = "",
    link: str = "",
    teslim_tipi: str = "esnek",
    kesin_bitis: datetime | None = None,
    en_erken_baslangic: date | None = None,
) -> Task:
    """Görevin alanlarını topluca günceller."""
    if not title.strip():
        raise ValueError("Görev başlığı boş olamaz.")
    if priority not in (1, 2, 3):
        raise ValueError("Öncelik 1, 2 veya 3 olmalı.")
    if duration_minutes <= 0:
        raise ValueError("Süre 0'dan büyük olmalı.")
    due_date, kesin_bitis = _teslim_bilgisini_dogrula(teslim_tipi, due_date, kesin_bitis)
    _en_erken_baslangici_dogrula(due_date, en_erken_baslangic)

    with SessionLocal() as session:
        task = _sahiplenilen_gorevi_getir(session, user_id, task_id)

        # Erteleme sayacı: görev zaten gecikmişken (tamamlanmadan) yeni tarih
        # eskisinden daha ileriyse gerçek bir "erteleme" yapılmış demektir.
        # Kesin teslimli görevlerde kesin_bitis'in ileri alınması da erteleme sayılır.
        if (
            task.due_date is not None
            and not task.done
            and task.due_date < date.today()
            and due_date is not None
            and due_date > task.due_date
        ):
            task.postponement_count += 1
        elif (
            task.teslim_tipi == "kesin"
            and task.kesin_bitis is not None
            and not task.done
            and kesin_bitis is not None
            and kesin_bitis > task.kesin_bitis
        ):
            task.postponement_count += 1

        task.title = title.strip()
        task.description = description
        task.priority = priority
        task.due_date = due_date
        task.duration_minutes = duration_minutes
        task.konum = konum
        task.link = link
        task.teslim_tipi = teslim_tipi
        task.kesin_bitis = kesin_bitis
        task.en_erken_baslangic = en_erken_baslangic
        session.commit()
        session.refresh(task)
        return task

def delete_task(user_id: int, task_id: int) -> None:
    """Görevi kalıcı olarak siler."""
    with SessionLocal() as session:
        task = _sahiplenilen_gorevi_getir(session, user_id, task_id)
        session.delete(task)
        session.commit()
