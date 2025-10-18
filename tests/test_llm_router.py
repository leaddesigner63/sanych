from __future__ import annotations

from fastapi.testclient import TestClient

from tgac.api.main import app
from tgac.api.routers.llm import get_llm_service
from tgac.api.services.llm import LlmGenerationResult, LlmUsage


class DummyLlmService:
    def __init__(self) -> None:
        self.comment_calls: list = []
        self.profile_calls: list = []

    def generate_comment(self, prompt):
        self.comment_calls.append(prompt)
        return LlmGenerationResult(
            suggestions=["Готовый комментарий"],
            usage=LlmUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        )

    def generate_profile_bio(self, prompt):
        self.profile_calls.append(prompt)
        return LlmGenerationResult(
            suggestions=["Описание профиля"],
            usage=LlmUsage(prompt_tokens=12, completion_tokens=18, total_tokens=30),
        )


def setup_module(module):
    module.client = TestClient(app)
    module.stub = DummyLlmService()
    app.dependency_overrides[get_llm_service] = lambda: module.stub


def teardown_module(module):
    app.dependency_overrides.pop(get_llm_service, None)


def test_comment_generation_endpoint_returns_payload():
    response = client.post(
        "/llm/comment",
        json={
            "topic": "Новый релиз",
            "persona": "Команда",
            "hashtags": ["tgac"],
            "count": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["suggestions"] == ["Готовый комментарий"]
    assert payload["data"]["usage"]["total_tokens"] == 25
    assert stub.comment_calls


def test_profile_generation_endpoint_returns_payload():
    response = client.post(
        "/llm/profile",
        json={
            "niche": "Автокомментинг",
            "highlights": ["24/7", "Умные шаблоны"],
            "include_call_to_action": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["suggestions"] == ["Описание профиля"]
    assert payload["data"]["usage"]["prompt_tokens"] == 12
    assert stub.profile_calls


def test_invalid_request_returns_validation_error():
    response = client.post(
        "/llm/comment",
        json={
            "topic": "ok",
            "count": 10,
        },
    )
    assert response.status_code == 422

