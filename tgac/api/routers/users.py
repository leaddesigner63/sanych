from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import User, UserRole
from ..schemas.common import DataResponse

router = APIRouter(prefix="/admin/users", tags=["users"])


@router.get("", response_model=DataResponse)
def list_users(db: Session = Depends(get_db)) -> DataResponse:
    users = db.query(User).all()
    return DataResponse(data=[{"id": user.id, "username": user.username, "role": user.role.value} for user in users])


@router.post("", response_model=DataResponse)
def create_user(payload: dict, db: Session = Depends(get_db)) -> DataResponse:
    role = UserRole(payload.get("role", UserRole.USER.value))
    user = User(username=payload["username"], role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return DataResponse(data={"id": user.id, "username": user.username})
