"""HTTP routes for channel management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Channel
from ..schemas import (
    ChannelAssignAccountsRequest,
    ChannelCreate,
    ChannelImportRequest,
)
from ..schemas.common import DataResponse
from ..services.channels import ChannelService, ChannelServiceError

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=DataResponse)
def list_channels(
    project_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> DataResponse:
    query = db.query(Channel)
    if project_id is not None:
        query = query.filter(Channel.project_id == project_id)

    query = query.order_by(Channel.id.desc())
    if limit is not None and limit > 0:
        query = query.limit(limit)

    channels = query.all()
    return DataResponse(
        data=[
            {
                "id": channel.id,
                "project_id": channel.project_id,
                "title": channel.title,
                "username": channel.username,
                "active": channel.active,
                "last_scanned_at": channel.last_scanned_at.isoformat()
                if channel.last_scanned_at
                else None,
            }
            for channel in channels
        ]
    )


@router.post("", response_model=DataResponse)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db)) -> DataResponse:
    channel = Channel(**payload.model_dump())
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return DataResponse(data={"id": channel.id, "title": channel.title})


@router.post("/import", response_model=DataResponse)
def import_channels(payload: ChannelImportRequest, db: Session = Depends(get_db)) -> DataResponse:
    created: list[Channel] = []
    for item in payload.channels:
        channel = Channel(**item.model_dump())
        db.add(channel)
        created.append(channel)

    if created:
        db.commit()
        for channel in created:
            db.refresh(channel)

    return DataResponse(
        data={
            "count": len(created),
            "ids": [channel.id for channel in created],
        }
    )


@router.post("/{channel_id}/assign_accounts", response_model=DataResponse)
def assign_accounts(
    channel_id: int,
    payload: ChannelAssignAccountsRequest,
    db: Session = Depends(get_db),
) -> DataResponse:
    service = ChannelService(db)
    try:
        created = service.assign_accounts(channel_id, payload.account_ids)
    except ChannelServiceError as exc:  # pragma: no cover - exercised via API tests
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return DataResponse(
        data={
            "channel_id": channel_id,
            "added": [mapping.account_id for mapping in created],
            "total_added": len(created),
        }
    )


__all__ = ["router"]
