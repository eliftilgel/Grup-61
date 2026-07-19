"""Planner REST API"""
from ast import List

from fastapi import FastAPI, HTTPException

from api.schemas import TaskCreate, TaskOut
from core.services import task_service

app = FastAPI(title="Planner API", version="0.1.0")

@app.get("/tasks", response_model=List[TaskOut])
def gorevleri_listele(include_done: bool = True):
    """Görevleri öncelik sırasına göre döner."""
    return task_service.list_tasks(include_done=include_done)

@app.post("/tasks", response_model=TaskOut, status_code=201)
def gorev_olustur(veri: TaskCreate):
    """Yeni görev oluşturur."""
    try:
        return task_service.create_task(
            veri.title, veri.description, veri.priority, veri.due_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.patch("/tasks/{task_id}/complete", response_model=TaskOut)
def gorev_tamamla(task_id:int):
    """Görevi tamamlandı işaretler."""
    try:
        return task_service.complete_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/tasks/{task_id}", status_code=204)
def gorev_sil(task_id:int):
    """Görevi kalıcı olarak siler."""
    try:
        task_service.delete_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))