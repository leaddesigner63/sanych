"""OpenAI-backed helpers for generating marketing copy."""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Iterable, Protocol, Sequence

from ..utils.settings import Settings, get_settings

try:  # pragma: no cover - import guard for optional dependency
    from openai import OpenAI, OpenAIError
except Exception:  # pragma: no cover - fall back if package is missing
    OpenAI = None  # type: ignore[assignment]

    class OpenAIError(Exception):
        """Fallback base exception when openai package is unavailable."""


class ChatCompletionsClient(Protocol):
    """Subset of the OpenAI chat completions client used by the service."""

    def create(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int,
        n: int,
    ) -> Any:
        ...


@dataclass(slots=True)
class CommentPrompt:
    """Parameters for generating contextual Telegram comments."""

    topic: str
    context: str | None = None
    persona: str | None = None
    tone: str | None = None
    language: str = "ru"
    hashtags: Sequence[str] = ()
    call_to_action: str | None = None
    audience: str | None = None
    avoid_phrases: Sequence[str] = ()
    style: str | None = None
    max_characters: int = 280
    temperature: float = 0.7
    max_tokens: int | None = None
    count: int = 1


@dataclass(slots=True)
class ProfilePrompt:
    """Parameters for generating Telegram profile bios."""

    niche: str
    persona: str | None = None
    highlights: Sequence[str] = ()
    tone: str | None = None
    language: str = "ru"
    include_call_to_action: bool = True
    call_to_action: str | None = None
    max_characters: int = 220
    temperature: float = 0.6
    max_tokens: int | None = None


@dataclass(slots=True)
class LlmUsage:
    """Token usage metadata returned by OpenAI."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def as_dict(self) -> dict[str, int]:
        payload: dict[str, int] = {}
        if self.prompt_tokens is not None:
            payload["prompt_tokens"] = self.prompt_tokens
        if self.completion_tokens is not None:
            payload["completion_tokens"] = self.completion_tokens
        if self.total_tokens is not None:
            payload["total_tokens"] = self.total_tokens
        return payload


@dataclass(slots=True)
class LlmGenerationResult:
    """Wrapper for textual suggestions produced by the LLM."""

    suggestions: list[str]
    usage: LlmUsage | None = None

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"suggestions": self.suggestions}
        if self.usage:
            usage_dict = self.usage.as_dict()
            if usage_dict:
                payload["usage"] = usage_dict
        return payload


class LlmServiceError(Exception):
    """Base exception for LLM service failures."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class LlmConfigurationError(LlmServiceError):
    """Raised when OpenAI integration is misconfigured."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message, status_code=status_code)


class LlmProviderError(LlmServiceError):
    """Raised when the OpenAI API fails to return a valid response."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code)


class LlmService:
    """High-level helper for producing marketing texts via OpenAI."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: ChatCompletionsClient | None = None,
        api_key: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        default_max_tokens: int | None = None,
    ) -> None:
        try:
            resolved_settings = settings or get_settings()
        except Exception:  # pragma: no cover - fallback when settings are unavailable
            resolved_settings = None

        self._settings = resolved_settings
        self.model = model or getattr(resolved_settings, "openai_model", "gpt-3.5-turbo")
        self.default_max_tokens = default_max_tokens or getattr(
            resolved_settings, "openai_max_tokens", 240
        )
        self.system_prompt = system_prompt or (
            "You are a senior marketing copywriter who crafts concise, natural Telegram texts. "
            "Always write in the requested language, keep outputs within the requested length, "
            "and never mention that you are an AI."
        )

        if client is not None:
            self._client = client
            self._openai_client = None
            return

        api_key = api_key or getattr(resolved_settings, "openai_api_key", None)
        if not api_key:
            raise LlmConfigurationError("OpenAI API key is not configured", status_code=503)
        if OpenAI is None:  # pragma: no cover - dependency missing
            raise LlmConfigurationError("openai package is not installed", status_code=503)

        openai_client = OpenAI(api_key=api_key)
        self._openai_client = openai_client
        self._client = openai_client.chat.completions

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_comment(self, prompt: CommentPrompt) -> LlmGenerationResult:
        """Produce one or more Telegram comment suggestions."""

        messages = self._build_messages(self._render_comment_prompt(prompt))
        max_tokens = prompt.max_tokens or self.default_max_tokens
        result = self._invoke(
            messages,
            temperature=prompt.temperature,
            max_tokens=max_tokens,
            count=prompt.count,
        )
        return result

    def generate_profile_bio(self, prompt: ProfilePrompt) -> LlmGenerationResult:
        """Produce a channel/profile biography snippet."""

        messages = self._build_messages(self._render_profile_prompt(prompt))
        max_tokens = prompt.max_tokens or self.default_max_tokens
        return self._invoke(
            messages,
            temperature=prompt.temperature,
            max_tokens=max_tokens,
            count=1,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_messages(self, user_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _invoke(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        count: int,
    ) -> LlmGenerationResult:
        try:
            response = self._client.create(
                model=self.model,
                messages=list(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                n=count,
            )
        except OpenAIError as exc:
            raise LlmProviderError("OpenAI request failed") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise LlmProviderError("Unexpected error while contacting OpenAI") from exc

        suggestions = self._extract_suggestions(response)
        usage = self._extract_usage(response)
        unique = self._deduplicate(suggestions)
        return LlmGenerationResult(suggestions=unique, usage=usage)

    def _render_comment_prompt(self, prompt: CommentPrompt) -> str:
        lines = [
            f"Сформулируй естественный комментарий для Telegram на языке {prompt.language}.",
            f"Тема обсуждения: {prompt.topic}.",
        ]
        if prompt.context:
            lines.append(f"Контекст поста: {prompt.context}.")
        if prompt.audience:
            lines.append(f"Целевая аудитория: {prompt.audience}.")
        if prompt.persona:
            lines.append(f"Пиши от лица: {prompt.persona}.")
        if prompt.tone:
            lines.append(f"Тон сообщения: {prompt.tone}.")
        if prompt.style:
            lines.append(f"Стиль оформления: {prompt.style}.")
        if prompt.call_to_action:
            lines.append(f"Обязательно добавь призыв: {prompt.call_to_action}.")
        if prompt.hashtags:
            lines.append(
                "Используй хэштеги: "
                + ", ".join(self._normalize_hashtags(prompt.hashtags))
                + "."
            )
        if prompt.avoid_phrases:
            lines.append(
                "Не используй фразы: " + "; ".join(str(p).strip() for p in prompt.avoid_phrases) + "."
            )
        lines.append(
            f"Максимальная длина текста {prompt.max_characters} символов, без эмодзи если не просили иначе."
        )
        lines.append("Ответ должен быть готовым комментарием без объяснений.")
        return "\n".join(lines)

    def _render_profile_prompt(self, prompt: ProfilePrompt) -> str:
        bullet_points = "\n".join(f"- {item}" for item in prompt.highlights if item)
        body = dedent(
            f"""
            Составь лаконичное описание профиля Telegram на языке {prompt.language}.
            Ниша/тематика: {prompt.niche}.
            {f'Пиши от лица: {prompt.persona}.' if prompt.persona else ''}
            {f'Тон описания: {prompt.tone}.' if prompt.tone else ''}
            Максимальная длина {prompt.max_characters} символов.
            {f'Ключевые преимущества:\n{bullet_points}' if bullet_points else ''}
            {('Добавь мягкий призыв к действию.' if prompt.include_call_to_action else 'Не включай призыв к действию.')}
            {f'Если нужен конкретный призыв, используй: {prompt.call_to_action}.' if prompt.call_to_action else ''}
            Ответ должен состоять только из текста профиля.
            """
        ).strip()
        return "\n".join(line for line in body.splitlines() if line.strip())

    @staticmethod
    def _normalize_hashtags(hashtags: Iterable[str]) -> list[str]:
        normalized = []
        for tag in hashtags:
            if not tag:
                continue
            tag_str = str(tag).strip()
            if not tag_str:
                continue
            if not tag_str.startswith("#"):
                tag_str = "#" + tag_str
            normalized.append(tag_str)
        return normalized

    @staticmethod
    def _deduplicate(suggestions: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for suggestion in suggestions:
            text = suggestion.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        if not result:
            raise LlmProviderError("OpenAI returned empty suggestions", status_code=502)
        return result

    @staticmethod
    def _extract_suggestions(response: Any) -> list[str]:
        choices = getattr(response, "choices", None) or response.get("choices", [])  # type: ignore[arg-type]
        texts: list[str] = []
        for choice in choices:
            message = getattr(choice, "message", None) or getattr(choice, "delta", None)
            if message is None and isinstance(choice, dict):
                message = choice.get("message") or choice.get("delta")
            if message is None:
                continue
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            if isinstance(content, list):
                parts = []
                for block in content:
                    text = getattr(block, "text", None)
                    if text is None and isinstance(block, dict):
                        text = block.get("text")
                    if text:
                        parts.append(str(text))
                content = "\n".join(parts)
            if content is None:
                continue
            texts.append(str(content))
        return texts

    @staticmethod
    def _extract_usage(response: Any) -> LlmUsage | None:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        if usage is None:
            return None
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
            completion_tokens = usage.get("completion_tokens", completion_tokens)
            total_tokens = usage.get("total_tokens", total_tokens)
        if not any(value is not None for value in (prompt_tokens, completion_tokens, total_tokens)):
            return None
        return LlmUsage(
            prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
            completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
            total_tokens=int(total_tokens) if total_tokens is not None else None,
        )


__all__ = [
    "ChatCompletionsClient",
    "CommentPrompt",
    "LlmGenerationResult",
    "LlmProviderError",
    "LlmService",
    "LlmServiceError",
    "LlmUsage",
    "ProfilePrompt",
    "LlmConfigurationError",
]

