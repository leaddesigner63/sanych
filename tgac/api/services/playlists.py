"""Domain services for playlist management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from ..models.core import Channel, Playlist, PlaylistChannel


class PlaylistServiceError(Exception):
    """Base playlist related error."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class PlaylistNotFound(PlaylistServiceError):
    """Raised when playlist cannot be located."""


class PlaylistChannelNotFound(PlaylistServiceError):
    """Raised when referenced channels do not exist."""


class PlaylistProjectMismatch(PlaylistServiceError):
    """Raised when playlist and channels belong to different projects."""


@dataclass
class PlaylistService:
    """Encapsulates playlist operations."""

    db: Session

    def assign_channels(self, playlist_id: int, channel_ids: Sequence[int]) -> list[PlaylistChannel]:
        """Assign channels to a playlist ensuring project consistency."""

        unique_channel_ids = list(dict.fromkeys(channel_ids))
        if not unique_channel_ids:
            return []

        playlist = self.db.get(Playlist, playlist_id)
        if playlist is None:
            raise PlaylistNotFound(f"Playlist {playlist_id} not found", status_code=404)

        channels = (
            self.db.query(Channel)
            .filter(Channel.id.in_(unique_channel_ids))
            .all()
        )
        found_ids = {channel.id for channel in channels}
        missing = [channel_id for channel_id in unique_channel_ids if channel_id not in found_ids]
        if missing:
            raise PlaylistChannelNotFound(
                f"Channels not found: {', '.join(str(mid) for mid in missing)}",
                status_code=404,
            )

        for channel in channels:
            if channel.project_id != playlist.project_id:
                raise PlaylistProjectMismatch("Playlist and channels must belong to the same project")

        existing_links = (
            self.db.query(PlaylistChannel)
            .filter(
                PlaylistChannel.playlist_id == playlist_id,
                PlaylistChannel.channel_id.in_(unique_channel_ids),
            )
            .all()
        )
        already_assigned = {link.channel_id for link in existing_links}

        created: list[PlaylistChannel] = []
        for channel in channels:
            if channel.id in already_assigned:
                continue
            mapping = PlaylistChannel(playlist_id=playlist_id, channel_id=channel.id)
            self.db.add(mapping)
            created.append(mapping)

        if created:
            self.db.commit()
            for mapping in created:
                self.db.refresh(mapping)
        else:
            self.db.flush()

        return created


__all__ = [
    "PlaylistService",
    "PlaylistServiceError",
    "PlaylistNotFound",
    "PlaylistChannelNotFound",
    "PlaylistProjectMismatch",
]
