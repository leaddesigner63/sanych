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
from .history import HistoryEntry, HistoryResponse
from .playlists import PlaylistAssignChannelsRequest, PlaylistCreateRequest, PlaylistUpdateRequest
from .proxies import (
    ProxyCheckRequest,
    ProxyCreateRequest,
    ProxyImportItem,
    ProxyImportRequest,
    ProxyImportResponse,
    ProxyResponse,
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
    "HistoryEntry",
    "HistoryResponse",
    "PlaylistAssignChannelsRequest",
    "PlaylistCreateRequest",
    "PlaylistUpdateRequest",
    "ProxyCheckRequest",
    "ProxyCreateRequest",
    "ProxyImportItem",
    "ProxyImportRequest",
    "ProxyImportResponse",
    "ProxyResponse",
    "TaskAssignRequest",
    "TaskAssignResponse",
    "TaskCreateRequest",
    "TaskResponse",
    "TaskStatsResponse",
    "TaskUpdateRequest",
]
