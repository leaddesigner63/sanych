"""Pydantic schemas package."""

from .accounts import (
    AccountHealthcheckRequest,
    AccountHealthcheckResponse,
    AccountImportItem,
    AccountImportRequest,
    AccountImportResponse,
    AccountPauseResponse,
    AssignProxyRequest,
)
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
    "AccountHealthcheckRequest",
    "AccountHealthcheckResponse",
    "AccountImportItem",
    "AccountImportRequest",
    "AccountImportResponse",
    "AccountPauseResponse",
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
