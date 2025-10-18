from __future__ import annotations

from types import SimpleNamespace

import pytest

from tgac.api.services.llm import (
    CommentPrompt,
    LlmConfigurationError,
    LlmProviderError,
    LlmService,
    ProfilePrompt,
)


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = SimpleNamespace(content=content)


class FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class FakeResponse:
    def __init__(self, choices: list[FakeChoice], usage: FakeUsage | None = None) -> None:
        self.choices = choices
        self.usage = usage


class FakeCompletions:
    def __init__(self, *, text_prefix: str = "Вариант") -> None:
        self.calls: list[dict] = []
        self.text_prefix = text_prefix

    def create(self, **kwargs):
        self.calls.append(kwargs)
        count = kwargs.get("n", 1)
        choices = [FakeChoice(f" {self.text_prefix} {idx + 1} \n") for idx in range(count)]
        usage = FakeUsage(prompt_tokens=12, completion_tokens=25, total_tokens=37)
        return FakeResponse(choices, usage=usage)


def test_generate_comment_builds_prompt_and_returns_suggestions():
    completions = FakeCompletions()
    settings = SimpleNamespace(openai_api_key=None, openai_model="test-model", openai_max_tokens=150)
    service = LlmService(settings=settings, client=completions)

    prompt = CommentPrompt(
        topic="Запуск новой рассылки",
        context="Автокомментинг помогает вести живые обсуждения",
        persona="Команда TGAC",
        tone="дружелюбный",
        language="ru",
        hashtags=["tgac", "маркетинг"],
        call_to_action="подписаться на обновления",
        audience="владельцы каналов",
        avoid_phrases=["бесплатно"],
        style="коротко",
        max_characters=180,
        temperature=0.55,
        max_tokens=120,
        count=2,
    )

    result = service.generate_comment(prompt)

    assert result.suggestions == ["Вариант 1", "Вариант 2"]
    assert result.usage and result.usage.total_tokens == 37

    payload = completions.calls[0]
    assert payload["model"] == "test-model"
    assert payload["n"] == 2
    user_prompt = payload["messages"][1]["content"]
    assert "Запуск новой рассылки" in user_prompt
    assert "#tgac" in user_prompt and "#маркетинг" in user_prompt
    assert "Не используй фразы" in user_prompt


def test_generate_profile_bio_includes_highlights_and_returns_single_suggestion():
    completions = FakeCompletions(text_prefix="Профиль")
    settings = SimpleNamespace(openai_api_key=None, openai_model="bio-model", openai_max_tokens=200)
    service = LlmService(settings=settings, client=completions)

    prompt = ProfilePrompt(
        niche="Продвижение Telegram-каналов",
        persona="Эксперты TGAC",
        highlights=["24/7 модерация", "Автокомментинг"],
        tone="уверенный",
        language="ru",
        include_call_to_action=False,
        max_characters=210,
        temperature=0.45,
        max_tokens=180,
    )

    result = service.generate_profile_bio(prompt)

    assert result.suggestions == ["Профиль 1"]
    call = completions.calls[0]
    assert call["model"] == "bio-model"
    assert call["max_tokens"] == 180
    prompt_text = call["messages"][1]["content"]
    assert "24/7 модерация" in prompt_text
    assert "Не включай призыв" in prompt_text


def test_provider_errors_are_wrapped():
    class FailingCompletions(FakeCompletions):
        def create(self, **kwargs):  # pragma: no cover - simple override
            raise RuntimeError("boom")

    service = LlmService(
        settings=SimpleNamespace(openai_api_key=None, openai_model="test", openai_max_tokens=100),
        client=FailingCompletions(),
    )

    with pytest.raises(LlmProviderError):
        service.generate_comment(CommentPrompt(topic="Тест"))


def test_missing_api_key_raises_when_no_client():
    settings = SimpleNamespace(openai_api_key=None, openai_model="test", openai_max_tokens=120)
    with pytest.raises(LlmConfigurationError):
        LlmService(settings=settings, client=None)

