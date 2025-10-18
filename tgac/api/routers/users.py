from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import asc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import User
from ..schemas import UserCreateRequest, UserResponse, UserUpdateRequest
from ..schemas.common import DataResponse

router = APIRouter(prefix="/admin/users", tags=["users"])


def _serialize_user(user: User) -> dict:
    return UserResponse.model_validate(user, from_attributes=True).model_dump(mode="json")


@router.get("", response_model=DataResponse)
def list_users(db: Session = Depends(get_db)) -> DataResponse:
    users = db.query(User).order_by(asc(User.id)).all()
    return DataResponse(data=[_serialize_user(user) for user in users])


@router.post("", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db)) -> DataResponse:
    user = User(
        username=payload.username,
        role=payload.role,
        telegram_id=payload.telegram_id,
        quota_projects=payload.quota_projects,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    db.refresh(user)
    return DataResponse(data=_serialize_user(user))


@router.put("/{user_id}", response_model=DataResponse)
def update_user(
    user_id: int, payload: UserUpdateRequest, db: Session = Depends(get_db)
) -> DataResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = payload.model_dump(exclude_unset=True)
    if "username" in updates:
        user.username = updates["username"]
    if "role" in updates and updates["role"] is not None:
        user.role = updates["role"]
    if "telegram_id" in updates:
        user.telegram_id = updates["telegram_id"]
    if "quota_projects" in updates:
        user.quota_projects = updates["quota_projects"]
    if "is_active" in updates and updates["is_active"] is not None:
        user.is_active = updates["is_active"]

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    db.refresh(user)
    return DataResponse(data=_serialize_user(user))


@router.post("/{user_id}/block", response_model=DataResponse)
def block_user(user_id: int, db: Session = Depends(get_db)) -> DataResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    db.commit()
    db.refresh(user)
    return DataResponse(data=_serialize_user(user))
