"""Pydantic schemas for proxy endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.core import ProxyScheme


class ProxyBase(BaseModel):
    name: str = Field(..., max_length=120)
    scheme: ProxyScheme = ProxyScheme.HTTP
    host: str = Field(..., max_length=255)
    port: int = Field(..., ge=1, le=65535)
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=120)


class ProxyCreateRequest(ProxyBase):
    project_id: int = Field(..., ge=1)


class ProxyResponse(BaseModel):
    id: int
    project_id: int
    name: str
    scheme: ProxyScheme
    host: str
    port: int
    is_working: bool
    last_check_at: datetime | None = None
    username: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProxyImportItem(ProxyBase):
    pass


class ProxyImportRequest(BaseModel):
    project_id: int = Field(..., ge=1)
    proxies: list[ProxyImportItem]


class ProxyImportResponse(BaseModel):
    created: list[int]
    skipped: list[str]
    count: int


class ProxyCheckRequest(BaseModel):
    is_working: bool


__all__ = [
    "ProxyCreateRequest",
    "ProxyResponse",
    "ProxyImportItem",
    "ProxyImportRequest",
    "ProxyImportResponse",
    "ProxyCheckRequest",
]
