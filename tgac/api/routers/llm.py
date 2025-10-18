"""Endpoints exposing LLM-powered helpers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas.common import DataResponse
from ..schemas.llm import CommentGenerationRequest, ProfileGenerationRequest
from ..services.llm import (
    LlmConfigurationError,
    LlmGenerationResult,
    LlmProviderError,
    LlmService,
)
from ..utils.settings import Settings, get_settings

router = APIRouter(prefix="/llm", tags=["llm"])


def get_llm_service(settings: Settings = Depends(get_settings)) -> LlmService:
    return LlmService(settings=settings)


def _handle_generation(result: LlmGenerationResult) -> DataResponse:
    return DataResponse(data=result.as_payload())


@router.post("/comment", response_model=DataResponse)
def generate_comment(
    payload: CommentGenerationRequest,
    service: LlmService = Depends(get_llm_service),
) -> DataResponse:
    try:
        result = service.generate_comment(payload.to_prompt())
    except (LlmProviderError, LlmConfigurationError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _handle_generation(result)


@router.post("/profile", response_model=DataResponse)
def generate_profile_bio(
    payload: ProfileGenerationRequest,
    service: LlmService = Depends(get_llm_service),
) -> DataResponse:
    try:
        result = service.generate_profile_bio(payload.to_prompt())
    except (LlmProviderError, LlmConfigurationError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _handle_generation(result)


__all__ = ["router", "get_llm_service"]

