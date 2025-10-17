from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Task, TaskStatus
from ..schemas.common import DataResponse
from ..schemas.tasks import (
    TaskAssignRequest,
    TaskAssignResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskStatsResponse,
    TaskUpdateRequest,
)
from ..services.tasks import AssignmentSummary, TaskService, TaskServiceError

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _serialize_task(task: Task) -> dict:
    return TaskResponse.model_validate(task, from_attributes=True).model_dump(mode="json")


def _handle_service_error(exc: TaskServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("", response_model=DataResponse)
def list_tasks(project_id: int | None = None, db: Session = Depends(get_db)) -> DataResponse:
    query = db.query(Task)
    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    tasks = query.order_by(Task.id.asc()).all()
    return DataResponse(data=[_serialize_task(task) for task in tasks])


@router.post("", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreateRequest, db: Session = Depends(get_db)) -> DataResponse:
    task = Task(
        project_id=payload.project_id,
        name=payload.name,
        mode=payload.mode,
        status=payload.status,
        config=payload.config or {},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return DataResponse(data=_serialize_task(task))


@router.put("/{task_id}", response_model=DataResponse)
def update_task(task_id: int, payload: TaskUpdateRequest, db: Session = Depends(get_db)) -> DataResponse:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if payload.name is not None:
        task.name = payload.name
    if payload.status is not None:
        task.status = payload.status
    if payload.mode is not None:
        task.mode = payload.mode
    if payload.config is not None:
        task.config = payload.config

    db.commit()
    db.refresh(task)
    return DataResponse(data=_serialize_task(task))


@router.post("/{task_id}/toggle", response_model=DataResponse)
def toggle_task(task_id: int, db: Session = Depends(get_db)) -> DataResponse:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = TaskStatus.OFF if task.status == TaskStatus.ON else TaskStatus.ON
    db.commit()
    db.refresh(task)
    return DataResponse(data={"id": task.id, "status": task.status.value})


def _assignment_response(task_id: int, summary: AssignmentSummary) -> TaskAssignResponse:
    return TaskAssignResponse(
        task_id=task_id,
        assigned=summary.applied,
        already_linked=summary.already_linked,
        skipped=summary.skipped,
        limit=summary.applied_limit,
    )


@router.post("/{task_id}/assign", response_model=DataResponse)
def assign_accounts(task_id: int, payload: TaskAssignRequest, db: Session = Depends(get_db)) -> DataResponse:
    service = TaskService(db)
    try:
        summary = service.assign_accounts(task_id, payload.account_ids)
    except TaskServiceError as exc:  # pragma: no cover - FastAPI handles in runtime
        raise _handle_service_error(exc)
    response = _assignment_response(task_id, summary)
    return DataResponse(data=response.model_dump(mode="json"))


@router.get("/{task_id}/stats", response_model=DataResponse)
def task_stats(task_id: int, db: Session = Depends(get_db)) -> DataResponse:
    service = TaskService(db)
    try:
        stats = service.stats(task_id)
    except TaskServiceError as exc:  # pragma: no cover - FastAPI handles in runtime
        raise _handle_service_error(exc)
    response = TaskStatsResponse(task_id=task_id, **stats)
    return DataResponse(data=response.model_dump(mode="json"))
