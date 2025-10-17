from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SettingOverride(BaseModel):
    key: str
    value: Any
    scope: str = Field(description="global or project scope identifier")
    project_id: int | None = None


class SettingsPayload(BaseModel):
    project_id: int | None = None


class SettingUpdateRequest(SettingsPayload):
    value: Any


class SettingsResponse(BaseModel):
    project_id: int | None
    defaults: dict[str, Any]
    overrides: list[SettingOverride]
    effective: dict[str, Any]
