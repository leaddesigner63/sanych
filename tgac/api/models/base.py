from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import UTCDateTime
from ..utils.time import utcnow


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )
