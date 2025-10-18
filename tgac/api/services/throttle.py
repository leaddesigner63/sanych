"""Adaptive throttling utilities for comment planning."""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models.core import Channel, Comment


@dataclass(slots=True)
class AdaptiveThrottle:
    """Calculate throttle factors based on comment visibility metrics."""

    db: Session
    target_visibility: float = 0.95
    step: float = 0.05
    min_factor: float = 0.0

    def project_factor(self, project_id: int) -> float:
        """Return throttle factor for the given project."""

        base_query = (
            self.db.query(Comment)
            .join(Channel, Channel.id == Comment.channel_id)
            .filter(
                Channel.project_id == project_id,
                Comment.visibility_checked_at.isnot(None),
            )
        )

        total = base_query.count()
        if total == 0:
            return 1.0

        visible = base_query.filter(Comment.visible.is_(True)).count()

        rate = visible / total if total else None
        return self._factor_from_rate(rate)

    def allowed_for(self, project_id: int, candidates: int) -> int:
        """Return number of candidates allowed after throttling."""

        if candidates <= 0:
            return 0

        factor = self.project_factor(project_id)
        if factor <= 0:
            return 0

        allowed = math.floor(candidates * factor)
        if allowed == 0:
            return 1
        return allowed

    def _factor_from_rate(self, visibility_rate: float | None) -> float:
        if visibility_rate is None:
            return 1.0
        if visibility_rate >= self.target_visibility:
            return 1.0

        deficit = self.target_visibility - visibility_rate
        steps = math.ceil(deficit / self.step)
        factor = 1.0 - steps * self.step
        return max(self.min_factor, round(factor, 4))


__all__ = ["AdaptiveThrottle"]
