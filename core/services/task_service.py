"""Görev İşlemleri - arayüzden bağımsız iş mantığı."""

from core.database import SessionLocal
from core.models import Task
from datetime import date

def create_task(title: str, description: str = "", priority: int = 1, due_date: date | None = None) -> Task:
    """Yeni görevi veritabanına kaydeder ve döner."""
    if not title.strip():
        raise ValueError("Görev başlığı boş olamaz")
    if priority not in (1, 2, 3):
        raise ValueError("Öncelik 1, 2 veya 3 olmalı")

    with SessionLocal() as session:
        task = Task(title=title, description=description, priority=priority)
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def list_tasks(include_done: bool = True) -> list[Task]:
    """Görevleri öncelik sırasına göre listeler."""
    with SessionLocal() as session:
        query = session.query(Task).order_by(Task.priority.desc(), Task.created_at.desc())
        if not include_done:
            query = query.filter(Task.done.is_(False))
        return list(query)


def complete_task(task_id: int) -> Task:
    """Görevi tamamlandı olarak işaretler."""
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if task is None:
            raise ValueError(f"{task_id} numaralı görev bulunamadı.")
        task.done = True
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