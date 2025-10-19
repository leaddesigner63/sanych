from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.core import Setting
from ..utils.settings import get_settings


@dataclass(frozen=True)
class SettingSpec:
    """Metadata describing a configurable setting."""

    key: str
    attr: str
    type_: type
    default: Any


class SettingsServiceError(Exception):
    """Base error for settings operations."""


class UnknownSetting(SettingsServiceError):
    """Raised when attempting to access an unsupported setting key."""


class InvalidSettingValue(SettingsServiceError):
    """Raised when provided value cannot be coerced into the expected type."""


SETTING_SPECS: dict[str, SettingSpec] = {
    "MAX_CHANNELS_PER_ACCOUNT": SettingSpec(
        key="MAX_CHANNELS_PER_ACCOUNT",
        attr="max_channels_per_account",
        type_=int,
        default=50,
    ),
    "COMMENT_COLLISION_LIMIT_PER_POST": SettingSpec(
        key="COMMENT_COLLISION_LIMIT_PER_POST",
        attr="comment_collision_limit_per_post",
        type_=int,
        default=1,
    ),
    "MAX_ACTIVE_THREADS_PER_ACCOUNT": SettingSpec(
        key="MAX_ACTIVE_THREADS_PER_ACCOUNT",
        attr="max_active_threads_per_account",
        type_=int,
        default=50,
    ),
    "COMMENT_VISIBILITY_STALE_MINUTES": SettingSpec(
        key="COMMENT_VISIBILITY_STALE_MINUTES",
        attr="comment_visibility_stale_minutes",
        type_=int,
        default=5,
    ),
    "CHANNEL_SCAN_INTERVAL_MINUTES": SettingSpec(
        key="CHANNEL_SCAN_INTERVAL_MINUTES",
        attr="channel_scan_interval_minutes",
        type_=int,
        default=15,
    ),
    "CHANNEL_SCAN_BATCH_SIZE": SettingSpec(
        key="CHANNEL_SCAN_BATCH_SIZE",
        attr="channel_scan_batch_size",
        type_=int,
        default=50,
    ),
}


class SettingsService:
    """Manages project-level settings with global overrides."""

    def __init__(
        self,
        db: Session,
        defaults: Mapping[str, Any] | None = None,
    ) -> None:
        self.db = db
        self._defaults = self._load_defaults(defaults)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def describe(self, project_id: int | None = None) -> dict[str, Any]:
        """Return defaults, overrides and effective values for a scope."""

        defaults = self._defaults.copy()
        overrides = list(self.iter_overrides(project_id))
        effective = defaults.copy()
        for item in overrides:
            effective[item["key"]] = item["value"]

        return {
            "project_id": project_id,
            "defaults": defaults,
            "overrides": overrides,
            "effective": effective,
        }

    def iter_overrides(
        self, project_id: int | None = None
    ) -> Iterable[dict[str, Any]]:
        """Yield overrides for the requested scope including global ones."""

        yield from self._serialize_overrides(self._global_overrides())
        if project_id is not None:
            yield from self._serialize_overrides(
                self._project_overrides(project_id), scope="project"
            )

    def get_effective(self, project_id: int | None = None) -> dict[str, Any]:
        """Return effective typed values for a given project scope."""

        return self.describe(project_id)["effective"]

    def set_value(
        self,
        key: str,
        value: Any,
        project_id: int | None = None,
    ) -> dict[str, Any]:
        """Create or update an override and return its representation."""

        spec = self._get_spec(key)
        coerced = self._coerce_value(spec, value)
        stored = json.dumps(coerced)

        identity = {"project_id": project_id, "key": key}
        setting = self.db.get(Setting, identity)
        if setting is None:
            setting = Setting(project_id=project_id, key=key, value=stored)
            self.db.add(setting)
        else:
            setting.value = stored

        self.db.commit()
        self.db.refresh(setting)
        scope = "project" if project_id is not None else "global"
        return {
            "key": key,
            "value": coerced,
            "project_id": project_id,
            "scope": scope,
        }

    def delete_value(self, key: str, project_id: int | None = None) -> bool:
        """Remove an override, returning True when removed."""

        spec = self._get_spec(key)
        _ = spec  # pragma: no cover - ensure validation happens
        identity = {"project_id": project_id, "key": key}
        setting = self.db.get(Setting, identity)
        if setting is None:
            return False
        self.db.delete(setting)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_defaults(
        self, provided: Mapping[str, Any] | None
    ) -> MutableMapping[str, Any]:
        runtime = None
        if provided is None:
            try:
                runtime = get_settings()
            except Exception:  # pragma: no cover - runtime env may be incomplete in tests
                runtime = None
        result: dict[str, Any] = {}
        for key, spec in SETTING_SPECS.items():
            value: Any | None = None
            if provided is not None:
                value = self._value_from_mapping(provided, key)
            if value is None and runtime is not None:
                value = getattr(runtime, spec.attr, None)
            if value is None:
                value = spec.default
            result[key] = self._coerce_value(spec, value)
        return result

    def _value_from_mapping(
        self, provided: Mapping[str, Any], key: str
    ) -> Any | None:
        if key in provided:
            return provided[key]
        lowered = key.lower()
        if lowered in provided:
            return provided[lowered]
        return None

    def _get_spec(self, key: str) -> SettingSpec:
        try:
            return SETTING_SPECS[key]
        except KeyError as exc:  # pragma: no cover - validated in tests
            raise UnknownSetting(f"Unsupported setting: {key}") from exc

    def _coerce_value(self, spec: SettingSpec, value: Any) -> Any:
        if spec.type_ is int:
            try:
                if isinstance(value, bool):  # prevent bool from being treated as int
                    raise ValueError
                return int(value)
            except (TypeError, ValueError) as exc:
                raise InvalidSettingValue(
                    f"Setting {spec.key} expects an integer"
                ) from exc
        if spec.type_ is bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off"}:
                    return False
            raise InvalidSettingValue(
                f"Setting {spec.key} expects a boolean"
            )
        if spec.type_ is str:
            if value is None:
                raise InvalidSettingValue(
                    f"Setting {spec.key} expects a non-empty string"
                )
            return str(value)
        raise InvalidSettingValue(
            f"Unsupported type for setting {spec.key}: {spec.type_.__name__}"
        )

    def _serialize_overrides(self, records, scope: str = "global"):
        for record in records:
            spec = self._get_spec(record.key)
            yield {
                "key": record.key,
                "value": self._deserialize_value(spec, record.value),
                "project_id": record.project_id,
                "scope": scope,
            }

    def _global_overrides(self):
        stmt = select(Setting).where(Setting.project_id.is_(None)).order_by(Setting.key.asc())
        return self.db.execute(stmt).scalars().all()

    def _project_overrides(self, project_id: int):
        stmt = (
            select(Setting)
            .where(Setting.project_id == project_id)
            .order_by(Setting.key.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def _deserialize_value(self, spec: SettingSpec, stored: str) -> Any:
        raw = json.loads(stored)
        return self._coerce_value(spec, raw)


__all__ = [
    "SettingsService",
    "SettingsServiceError",
    "UnknownSetting",
    "InvalidSettingValue",
    "SETTING_SPECS",
]
