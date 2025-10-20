from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models.core import Project, User, UserRole
from ..schemas import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest
from ..schemas.common import DataResponse
from ..services.projects import ProjectService, ProjectServiceError

router = APIRouter(prefix="/projects", tags=["projects"])


def _serialize_project(project: Project) -> dict:
    return ProjectResponse.model_validate(project, from_attributes=True).model_dump(mode="json")


@router.get("", response_model=DataResponse)
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = db.query(Project)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(Project.user_id == current_user.id)
    projects = query.order_by(Project.id.asc()).all()
    return DataResponse(data=[_serialize_project(project) for project in projects])


@router.post("", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    if current_user.role != UserRole.ADMIN and payload.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create project for another user",
        )

    service = ProjectService(db)
    try:
        project = service.create_project(
            user_id=payload.user_id,
            name=payload.name,
            status=payload.status,
        )
    except ProjectServiceError as exc:  # pragma: no cover - FastAPI handles response
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return DataResponse(data=_serialize_project(project))


@router.put("/{project_id}", response_model=DataResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if current_user.role != UserRole.ADMIN and project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project not accessible")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        project.name = updates["name"]
    if "status" in updates and updates["status"] is not None:
        project.status = updates["status"]

    db.commit()
    db.refresh(project)
    return DataResponse(data=_serialize_project(project))


@router.delete("/{project_id}", response_model=DataResponse, status_code=status.HTTP_200_OK)
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DataResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if current_user.role != UserRole.ADMIN and project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project not accessible")

    db.delete(project)
    db.commit()
    return DataResponse(data={"id": project_id, "deleted": True})
