"""Helpers for preparing application recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

# A mapping of canonical platform names to domains that are considered
# "official" stores for these platforms.
OFFICIAL_STORE_DOMAINS: dict[str, tuple[str, ...]] = {
    "android": ("play.google.com",),
    "ios": ("apps.apple.com",),
    "macos": ("apps.apple.com",),
    "windows": ("apps.microsoft.com", "www.microsoft.com"),
}

# Some common aliases that we normalise to the canonical form above.
PLATFORM_ALIASES: dict[str, str] = {
    "android": "android",
    "ios": "ios",
    "iphone": "ios",
    "ipad": "ios",
    "mac": "macos",
    "macos": "macos",
    "osx": "macos",
    "windows": "windows",
    "win": "windows",
    "win32": "windows",
    "win64": "windows",
    "linux": "linux",
}


def _normalise_platform(platform: str) -> str:
    """Convert the incoming platform label to a canonical form."""

    key = (platform or "").strip().lower()
    return PLATFORM_ALIASES.get(key, key)


@dataclass(frozen=True, slots=True)
class AppRecommendation:
    """A single application recommendation entry."""

    name: str
    platform: str
    url: str

    def normalised_platform(self) -> str:
        """Return the canonical platform name for filtering logic."""

        return _normalise_platform(self.platform)


@dataclass(frozen=True, slots=True)
class RecommendationFilterResult:
    """Outcome of filtering recommendations by official store domains."""

    allowed: list[AppRecommendation]
    rejected: list[AppRecommendation]


def _is_official_store_link(recommendation: AppRecommendation) -> bool:
    """Check whether the recommendation link belongs to an official store."""

    platform = recommendation.normalised_platform()
    # Linux recommendations may point to package repositories or project
    # websites, so we intentionally skip the store check here.
    if platform == "linux":
        return True

    allowed_domains = OFFICIAL_STORE_DOMAINS.get(platform)
    if not allowed_domains:
        return False

    parsed = urlparse(recommendation.url.strip())
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    for domain in allowed_domains:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return True
    return False


def filter_official_recommendations(
    recommendations: Iterable[AppRecommendation],
) -> RecommendationFilterResult:
    """Split recommendations into allowed and rejected groups."""

    allowed: list[AppRecommendation] = []
    rejected: list[AppRecommendation] = []

    for recommendation in recommendations:
        # Ensure we operate on dataclasses even if callers pass plain dicts.
        if not isinstance(recommendation, AppRecommendation):
            recommendation = AppRecommendation(**recommendation)  # type: ignore[arg-type]

        if _is_official_store_link(recommendation):
            allowed.append(recommendation)
        else:
            rejected.append(recommendation)

    return RecommendationFilterResult(allowed=allowed, rejected=rejected)


__all__ = [
    "AppRecommendation",
    "RecommendationFilterResult",
    "filter_official_recommendations",
]

