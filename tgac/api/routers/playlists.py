"""HTTP routes for playlist management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Playlist
from ..schemas import (
    PlaylistAssignChannelsRequest,
    PlaylistCreateRequest,
    PlaylistUpdateRequest,
)
from ..schemas.common import DataResponse
from ..services.playlists import PlaylistService, PlaylistServiceError

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.get("", response_model=DataResponse)
def list_playlists(db: Session = Depends(get_db)) -> DataResponse:
    playlists = db.query(Playlist).order_by(Playlist.id.desc()).limit(200).all()
    return DataResponse(
        data=[
            {
                "id": playlist.id,
                "project_id": playlist.project_id,
                "name": playlist.name,
                "desc": playlist.desc,
            }
            for playlist in playlists
        ]
    )


@router.post("", response_model=DataResponse)
def create_playlist(payload: PlaylistCreateRequest, db: Session = Depends(get_db)) -> DataResponse:
    playlist = Playlist(**payload.model_dump())
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return DataResponse(data={"id": playlist.id, "name": playlist.name})


@router.put("/{playlist_id}", response_model=DataResponse)
def update_playlist(
    playlist_id: int,
    payload: PlaylistUpdateRequest,
    db: Session = Depends(get_db),
) -> DataResponse:
    playlist = db.get(Playlist, playlist_id)
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(playlist, field, value)

    db.commit()
    db.refresh(playlist)
    return DataResponse(data={"id": playlist.id, "name": playlist.name, "desc": playlist.desc})


@router.post("/{playlist_id}/assign_channels", response_model=DataResponse)
def assign_channels(
    playlist_id: int,
    payload: PlaylistAssignChannelsRequest,
    db: Session = Depends(get_db),
) -> DataResponse:
    service = PlaylistService(db)
    try:
        created = service.assign_channels(playlist_id, payload.channel_ids)
    except PlaylistServiceError as exc:  # pragma: no cover - exercised via API tests
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return DataResponse(
        data={
            "playlist_id": playlist_id,
            "added": [mapping.channel_id for mapping in created],
            "total_added": len(created),
        }
    )


__all__ = ["router"]
