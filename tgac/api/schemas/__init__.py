"""Pydantic schemas package."""

from .accounts import AssignProxyRequest
from .channels import (
    ChannelAssignAccountsRequest,
    ChannelCreate,
    ChannelImportRequest,
)
from .playlists import (
    PlaylistAssignChannelsRequest,
    PlaylistCreateRequest,
    PlaylistUpdateRequest,
)
from .tasks import (
    TaskAssignRequest,
    TaskAssignResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskStatsResponse,
    TaskUpdateRequest,
)

__all__ = [
    "AssignProxyRequest",
    "ChannelAssignAccountsRequest",
    "ChannelCreate",
    "ChannelImportRequest",
    "PlaylistAssignChannelsRequest",
    "PlaylistCreateRequest",
    "PlaylistUpdateRequest",
    "TaskAssignRequest",
    "TaskAssignResponse",
    "TaskCreateRequest",
    "TaskResponse",
    "TaskStatsResponse",
    "TaskUpdateRequest",
]
