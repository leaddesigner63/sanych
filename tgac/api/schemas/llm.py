"""Pydantic models for LLM-related endpoints."""

from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, Field, field_validator

from ..services.llm import CommentPrompt, ProfilePrompt


class CommentGenerationRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=400)
    context: str | None = Field(None, max_length=800)
    persona: str | None = Field(None, max_length=200)
    tone: str | None = Field(None, max_length=120)
    language: str = Field("ru", min_length=2, max_length=32)
    hashtags: list[str] = Field(default_factory=list, max_length=8)
    call_to_action: str | None = Field(None, max_length=200)
    audience: str | None = Field(None, max_length=200)
    avoid_phrases: list[str] = Field(default_factory=list, max_length=10)
    style: str | None = Field(None, max_length=120)
    max_characters: int = Field(280, ge=60, le=500)
    temperature: float = Field(0.7, ge=0, le=1.5)
    max_tokens: int | None = Field(None, ge=32, le=800)
    count: int = Field(1, ge=1, le=5)

    @field_validator("hashtags", "avoid_phrases", mode="before")
    @classmethod
    def ensure_sequence(cls, value: Sequence[str] | str | None):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    def to_prompt(self) -> CommentPrompt:
        return CommentPrompt(
            topic=self.topic,
            context=self.context,
            persona=self.persona,
            tone=self.tone,
            language=self.language,
            hashtags=self.hashtags,
            call_to_action=self.call_to_action,
            audience=self.audience,
            avoid_phrases=self.avoid_phrases,
            style=self.style,
            max_characters=self.max_characters,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            count=self.count,
        )


class ProfileGenerationRequest(BaseModel):
    niche: str = Field(..., min_length=3, max_length=400)
    persona: str | None = Field(None, max_length=200)
    highlights: list[str] = Field(default_factory=list, max_length=6)
    tone: str | None = Field(None, max_length=120)
    language: str = Field("ru", min_length=2, max_length=32)
    include_call_to_action: bool = Field(True)
    call_to_action: str | None = Field(None, max_length=200)
    max_characters: int = Field(220, ge=80, le=400)
    temperature: float = Field(0.6, ge=0, le=1.5)
    max_tokens: int | None = Field(None, ge=32, le=800)

    @field_validator("highlights", mode="before")
    @classmethod
    def ensure_highlights(cls, value: Sequence[str] | str | None):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [item for item in value if item]

    def to_prompt(self) -> ProfilePrompt:
        return ProfilePrompt(
            niche=self.niche,
            persona=self.persona,
            highlights=self.highlights,
            tone=self.tone,
            language=self.language,
            include_call_to_action=self.include_call_to_action,
            call_to_action=self.call_to_action,
            max_characters=self.max_characters,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )


__all__ = [
    "CommentGenerationRequest",
    "ProfileGenerationRequest",
]

