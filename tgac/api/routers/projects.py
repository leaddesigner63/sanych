from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Project, ProjectStatus
from ..schemas.common import DataResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=DataResponse)
def list_projects(db: Session = Depends(get_db)) -> DataResponse:
    projects = db.query(Project).all()
    return DataResponse(data=[{"id": project.id, "name": project.name, "status": project.status.value} for project in projects])


@router.post("", response_model=DataResponse)
def create_project(payload: dict, db: Session = Depends(get_db)) -> DataResponse:
    status = ProjectStatus(payload.get("status", ProjectStatus.ACTIVE.value))
    project = Project(user_id=payload.get("user_id", 1), name=payload.get("name", "New Project"), status=status)
    db.add(project)
    db.commit()
    db.refresh(project)
    return DataResponse(data={"id": project.id, "name": project.name})
