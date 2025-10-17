from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas.common import DataResponse
from ..schemas.settings import SettingUpdateRequest
from ..services.settings import InvalidSettingValue, SettingsService, UnknownSetting

router = APIRouter(prefix="/settings", tags=["settings"])


def _service(db: Session) -> SettingsService:
    return SettingsService(db)


@router.get("", response_model=DataResponse)
def get_settings(project_id: int | None = None, db: Session = Depends(get_db)) -> DataResponse:
    service = _service(db)
    data = service.describe(project_id)
    return DataResponse(data=data)


@router.put("/{key}", response_model=DataResponse, status_code=status.HTTP_200_OK)
def put_setting(
    key: str, payload: SettingUpdateRequest, db: Session = Depends(get_db)
) -> DataResponse:
    service = _service(db)
    try:
        override = service.set_value(key, payload.value, payload.project_id)
    except UnknownSetting as exc:  # pragma: no cover - FastAPI handles in runtime
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidSettingValue as exc:  # pragma: no cover - FastAPI handles in runtime
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return DataResponse(data=override)


@router.delete("/{key}", response_model=DataResponse)
def delete_setting(
    key: str, project_id: int | None = None, db: Session = Depends(get_db)
) -> DataResponse:
    service = _service(db)
    try:
        deleted = service.delete_value(key, project_id)
    except UnknownSetting as exc:  # pragma: no cover - FastAPI handles in runtime
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return DataResponse(data={"deleted": deleted})
