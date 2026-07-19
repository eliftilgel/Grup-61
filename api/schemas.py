from datetime import date, datetime

from pydantic import BaseModel, Field

class TaskCreate(BaseModel):
    """Görev oluşturma isteğinin gövdesi."""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    priority: int = Field(default=1, ge=1, le=3)
    due_date: date | None = None

class TaskOut(BaseModel):
    """API'nin dışarı verdiği görev temsili."""

    id: int
    title: str
    description: str
    priority: int
    done: bool
    due_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}
    