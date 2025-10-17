from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Project
from ..schemas import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest
from ..schemas.common import DataResponse

router = APIRouter(prefix="/projects", tags=["projects"])


def _serialize_project(project: Project) -> dict:
    return ProjectResponse.model_validate(project, from_attributes=True).model_dump(mode="json")


@router.get("", response_model=DataResponse)
def list_projects(db: Session = Depends(get_db)) -> DataResponse:
    projects = db.query(Project).order_by(Project.id.asc()).all()
    return DataResponse(data=[_serialize_project(project) for project in projects])


@router.post("", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest, db: Session = Depends(get_db)) -> DataResponse:
    project = Project(
        user_id=payload.user_id,
        name=payload.name,
        status=payload.status,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return DataResponse(data=_serialize_project(project))


@router.put("/{project_id}", response_model=DataResponse)
def update_project(
    project_id: int, payload: ProjectUpdateRequest, db: Session = Depends(get_db)
) -> DataResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        project.name = updates["name"]
    if "status" in updates and updates["status"] is not None:
        project.status = updates["status"]

    db.commit()
    db.refresh(project)
    return DataResponse(data=_serialize_project(project))


@router.delete("/{project_id}", response_model=DataResponse, status_code=status.HTTP_200_OK)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> DataResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    db.delete(project)
    db.commit()
    return DataResponse(data={"id": project_id, "deleted": True})
