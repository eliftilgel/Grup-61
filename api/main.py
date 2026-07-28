"""Planner REST API

NOT: Bu API henüz çoklu-kullanıcı auth'a sahip değil. Her endpoint zorunlu
bir `user_id` parametresi alır ama kimin o id'yi kullanmaya yetkili olduğunu
doğrulamaz — bilinçli bir kapsam dışı bırakma (bkz. CLAUDE.md).
"""
from fastapi import FastAPI, HTTPException

from api.schemas import TaskCreate, TaskOut
from core.logging_config import setup_logging
from core.services import task_service

setup_logging()

app = FastAPI(title="Planner API", version="0.1.0")

@app.get("/tasks", response_model=list[TaskOut])
def gorevleri_listele(user_id: int, include_done: bool = True):
    """Görevleri öncelik sırasına göre döner."""
    return task_service.list_tasks(user_id, include_done=include_done)

@app.post("/tasks", response_model=TaskOut, status_code=201)
def gorev_olustur(user_id: int, veri: TaskCreate):
    """Yeni görev oluşturur."""
    try:
        return task_service.create_task(
            user_id, veri.title, veri.description, veri.priority, veri.due_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.patch("/tasks/{task_id}/complete", response_model=TaskOut)
def gorev_tamamla(task_id: int, user_id: int):
    """Görevi tamamlandı işaretler."""
    try:
        return task_service.complete_task(user_id, task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/tasks/{task_id}", status_code=204)
def gorev_sil(task_id: int, user_id: int):
    """Görevi kalıcı olarak siler."""
    try:
        task_service.delete_task(user_id, task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
