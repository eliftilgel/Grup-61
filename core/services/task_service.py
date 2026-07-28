"""Görev İşlemleri - arayüzden bağımsız iş mantığı."""

from core.database import SessionLocal
from core.models import Task
from datetime import date, datetime, timezone

def create_task(
    title: str,
    description: str = "",
    priority: int = 1,
    due_date: date | None = None,
    duration_minutes: int = 30,
) -> Task:
    """Yeni görevi veritabanına kaydeder ve döner."""
    if not title.strip():
        raise ValueError("Görev başlığı boş olamaz")
    if priority not in (1, 2, 3):
        raise ValueError("Öncelik 1, 2 veya 3 olmalı")
    if duration_minutes <= 0:
        raise ValueError("Süre 0'dan büyük olmalı")

    with SessionLocal() as session:
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            duration_minutes=duration_minutes,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def list_tasks(
    include_done: bool = True, only_done: bool = False, due_date: date | None = None
) -> list[Task]:
    """Görevleri öncelik sırasına göre listeler."""
    with SessionLocal() as session:
        query = session.query(Task).order_by(Task.priority.desc(), Task.created_at.desc())
        if only_done:
            query = query.filter(Task.done.is_(True))
        elif not include_done:
            query = query.filter(Task.done.is_(False))
        if due_date is not None:
            query = query.filter(Task.due_date == due_date)
        return list(query)


def complete_task(task_id: int) -> Task:
    """Görevi tamamlandı olarak işaretler."""
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task is None:
            raise ValueError(f"{task_id} numaralı görev bulunamadı.")
        task.done = True
        task.completed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(task)
        return task

def update_task(
    task_id: int,
    title: str,
    description: str,
    priority: int,
    due_date: date | None = None,
    duration_minutes: int = 30,
) -> Task:
    """Görevin alanlarını topluca günceller."""
    if not title.strip():
        raise ValueError("Görev başlığı boş olamaz.")
    if priority not in (1, 2, 3):
        raise ValueError("Öncelik 1, 2 veya 3 olmalı.")
    if duration_minutes <= 0:
        raise ValueError("Süre 0'dan büyük olmalı.")

    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task is None:
            raise ValueError(f"{task_id} numaralı görev bulunamadı.")

        # Erteleme sayacı: görev zaten gecikmişken (tamamlanmadan) yeni tarih
        # eskisinden daha ileriyse gerçek bir "erteleme" yapılmış demektir.
        if (
            task.due_date is not None
            and not task.done
            and task.due_date < date.today()
            and due_date is not None
            and due_date > task.due_date
        ):
            task.postponement_count += 1

        task.title = title.strip()
        task.description = description
        task.priority = priority
        task.due_date = due_date
        task.duration_minutes = duration_minutes
        session.commit()
        session.refresh(task)
        return task

def delete_task(task_id: int) -> None:
    """Görevi kalıcı olarak siler."""
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task is None:
            raise ValueError(f"{task_id} numaralı görev bulunamadı.")
        session.delete(task)
        session.commit()