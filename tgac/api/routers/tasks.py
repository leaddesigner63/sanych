from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Task, TaskMode, TaskStatus
from ..schemas.common import DataResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=DataResponse)
def list_tasks(db: Session = Depends(get_db)) -> DataResponse:
    tasks = db.query(Task).all()
    return DataResponse(
        data=[
            {
                "id": task.id,
                "name": task.name,
                "status": task.status.value,
                "mode": task.mode.value,
            }
            for task in tasks
        ]
    )


@router.post("", response_model=DataResponse)
def create_task(payload: dict, db: Session = Depends(get_db)) -> DataResponse:
    task = Task(
        project_id=payload.get("project_id", 1),
        name=payload.get("name", "New Task"),
        mode=TaskMode(payload.get("mode", TaskMode.NEW_POSTS.value)),
        status=TaskStatus(payload.get("status", TaskStatus.ON.value)),
        config=payload.get("config", {}),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return DataResponse(data={"id": task.id, "status": task.status.value})
