from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    admin_tg_username: str = Field("admin_username", env="ADMIN_TG_USERNAME")
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_deeplink_ttl_min: int = Field(10, env="TELEGRAM_DEEPLINK_TTL_MIN")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-3.5-turbo", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(240, env="OPENAI_MAX_TOKENS")
    sms_activate_api_key: Optional[str] = Field(None, env="SMS_ACTIVATE_API_KEY")
    sms_activate_poll_interval_seconds: int = Field(30, env="SMS_ACTIVATE_POLL_INTERVAL_SECONDS")
    sms_activate_max_poll_attempts: int = Field(10, env="SMS_ACTIVATE_MAX_POLL_ATTEMPTS")
    brightdata_username: Optional[str] = Field(None, env="BRIGHTDATA_USERNAME")
    brightdata_password: Optional[str] = Field(None, env="BRIGHTDATA_PASSWORD")
    timezone: str = Field("Europe/Amsterdam", env="TZ")
    base_url: str = Field(..., env="BASE_URL")

    db_url: str = Field(..., env="DB_URL")
    session_secret_key: str = Field(..., env="SESSION_SECRET_KEY")

    log_retention_days: int = Field(7, env="LOG_RETENTION_DAYS")
    max_channels_per_account: int = Field(50, env="MAX_CHANNELS_PER_ACCOUNT")
    comment_collision_limit_per_post: int = Field(1, env="COMMENT_COLLISION_LIMIT_PER_POST")
    max_active_threads_per_account: int = Field(50, env="MAX_ACTIVE_THREADS_PER_ACCOUNT")
    comment_visibility_stale_minutes: int = Field(5, env="COMMENT_VISIBILITY_STALE_MINUTES")
    account_healthcheck_interval_minutes: int = Field(
        180, env="ACCOUNT_HEALTHCHECK_INTERVAL_MINUTES"
    )
    account_healthcheck_batch_size: int = Field(
        100, env="ACCOUNT_HEALTHCHECK_BATCH_SIZE"
    )
    channel_scan_interval_minutes: int = Field(15, env="CHANNEL_SCAN_INTERVAL_MINUTES")
    channel_scan_batch_size: int = Field(50, env="CHANNEL_SCAN_BATCH_SIZE")
    default_project_quota: int = Field(5, env="DEFAULT_PROJECT_QUOTA")

    worker_shards: int = Field(1, env="WORKER_SHARDS")
    worker_shard: int = Field(0, env="WORKER_SHARD")
    max_concurrency: int = Field(10, env="MAX_CONCURRENCY")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    events_log_path: str = Field("tgac/logs/events.jsonl", env="EVENTS_LOG_PATH")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @field_validator("db_url", mode="before")
    @classmethod
    def ensure_sqlite_path(cls, value: str) -> str:
        if value.startswith("sqlite"):
            path = value.split("sqlite:///")[-1]
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
