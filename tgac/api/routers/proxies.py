from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Proxy
from ..schemas import (
    ProxyCheckRequest,
    ProxyCreateRequest,
    ProxyImportRequest,
    ProxyImportResponse,
    ProxyResponse,
)
from ..schemas.common import DataResponse
from ..services.proxies import (
    ProxyCreateData,
    ProxyImportData,
    ProxyService,
    ProxyServiceError,
)

router = APIRouter(prefix="/proxies", tags=["proxies"])


@router.get("", response_model=DataResponse)
def list_proxies(db: Session = Depends(get_db)) -> DataResponse:
    proxies = db.query(Proxy).order_by(Proxy.id).all()
    items = [ProxyResponse.model_validate(proxy).model_dump(mode="json") for proxy in proxies]
    return DataResponse(data=items)


@router.post("", response_model=DataResponse)
def create_proxy(payload: ProxyCreateRequest, db: Session = Depends(get_db)) -> DataResponse:
    service = ProxyService(db)
    try:
        proxy = service.create_proxy(
            ProxyCreateData(
                project_id=payload.project_id,
                name=payload.name,
                scheme=payload.scheme,
                host=payload.host,
                port=payload.port,
                username=payload.username,
                password=payload.password,
            )
        )
    except ProxyServiceError as exc:  # pragma: no cover - FastAPI translates to HTTP response
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    response = ProxyResponse.model_validate(proxy)
    return DataResponse(data=response.model_dump(mode="json"))


@router.post("/import", response_model=DataResponse)
def import_proxies(payload: ProxyImportRequest, db: Session = Depends(get_db)) -> DataResponse:
    service = ProxyService(db)
    entries = [
        ProxyImportData(
            name=item.name,
            scheme=item.scheme,
            host=item.host,
            port=item.port,
            username=item.username,
            password=item.password,
        )
        for item in payload.proxies
    ]
    summary = service.import_proxies(payload.project_id, entries)
    response = ProxyImportResponse(
        created=[proxy.id for proxy in summary.created],
        skipped=summary.skipped,
        count=len(summary.created),
    )
    return DataResponse(data=response.model_dump())


@router.post("/{proxy_id}/check", response_model=DataResponse)
def check_proxy(proxy_id: int, payload: ProxyCheckRequest, db: Session = Depends(get_db)) -> DataResponse:
    service = ProxyService(db)
    try:
        proxy = service.record_check(proxy_id, is_working=payload.is_working)
    except ProxyServiceError as exc:  # pragma: no cover - FastAPI translates to HTTP response
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    response = ProxyResponse.model_validate(proxy)
    return DataResponse(data=response.model_dump(mode="json"))
