from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.params import Query as QueryParam
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Account, AccountStatus
from ..schemas import (
    AccountHealthcheckRequest,
    AccountHealthcheckResponse,
    AccountImportRequest,
    AccountImportResponse,
    AccountPauseResponse,
    AssignProxyRequest,
)
from ..schemas.common import DataResponse
from ..services.accounts import (
    AccountImportData,
    AccountService,
    AccountServiceError,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=DataResponse)
def list_accounts(
    db: Session = Depends(get_db),
    project_id: int | None = None,
    status: list[AccountStatus] | None = Query(None),
    tags: list[str] | None = Query(None),
    is_paused: bool | None = None,
    proxy_id: int | None = None,
    limit: int = Query(100, ge=0, le=500),
) -> DataResponse:
    query = db.query(Account)

    if project_id is not None:
        query = query.filter(Account.project_id == project_id)

    if isinstance(status, QueryParam):  # pragma: no cover - FastAPI handles in runtime
        status = status.default
    if status:
        query = query.filter(Account.status.in_(status))

    if is_paused is not None:
        query = query.filter(Account.is_paused == is_paused)

    if proxy_id is not None:
        query = query.filter(Account.proxy_id == proxy_id)

    if isinstance(tags, QueryParam):  # pragma: no cover - FastAPI handles in runtime
        tags = tags.default
    if tags:
        for tag in tags:
            if not tag:
                continue
            query = query.filter(Account.tags.ilike(f"%{tag}%"))

    query = query.order_by(Account.id.asc())

    if limit:
        query = query.limit(limit)

    accounts = query.all()
    return DataResponse(
        data=[
            {
                "id": account.id,
                "phone": account.phone,
                "status": account.status.value,
                "project_id": account.project_id,
                "is_paused": account.is_paused,
                "last_health_at": account.last_health_at.isoformat()
                if account.last_health_at
                else None,
            }
            for account in accounts
        ]
    )


@router.post("", response_model=DataResponse)
def create_account(payload: dict, db: Session = Depends(get_db)) -> DataResponse:
    status = AccountStatus(payload.get("status", AccountStatus.NEEDS_LOGIN.value))
    account = Account(
        project_id=payload.get("project_id", 1),
        phone=payload["phone"],
        session_enc=b"",
        status=status,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return DataResponse(data={"id": account.id, "status": account.status.value})


@router.post("/import", response_model=DataResponse)
def import_accounts(payload: AccountImportRequest, db: Session = Depends(get_db)) -> DataResponse:
    service = AccountService(db)
    entries = [
        AccountImportData(
            phone=item.phone,
            status=item.status or AccountStatus.NEEDS_LOGIN,
            tags=item.tags,
            notes=item.notes,
        )
        for item in payload.accounts
    ]
    summary = service.import_accounts(payload.project_id, entries)
    response = AccountImportResponse(
        created=[account.id for account in summary.created],
        skipped=summary.skipped,
        count=len(summary.created),
    )
    return DataResponse(data=response.model_dump())


@router.post("/{account_id}/proxy", response_model=DataResponse)
def assign_proxy(
    account_id: int, payload: AssignProxyRequest, db: Session = Depends(get_db)
) -> DataResponse:
    service = AccountService(db)
    try:
        account = service.assign_proxy(account_id, payload.proxy_id)
    except AccountServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return DataResponse(data={"id": account.id, "proxy_id": account.proxy_id})


@router.post("/{account_id}/healthcheck", response_model=DataResponse)
def record_healthcheck(
    account_id: int,
    payload: AccountHealthcheckRequest,
    db: Session = Depends(get_db),
) -> DataResponse:
    service = AccountService(db)
    try:
        account = service.record_healthcheck(
            account_id,
            status=payload.status,
            notes=payload.notes,
        )
    except AccountServiceError as exc:  # pragma: no cover - FastAPI converts to response
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    response = AccountHealthcheckResponse(
        id=account.id,
        status=account.status,
        last_health_at=account.last_health_at,
        notes=account.notes,
    )
    return DataResponse(data=response.model_dump(mode="json"))


@router.post("/{account_id}/pause", response_model=DataResponse)
def pause_account(account_id: int, db: Session = Depends(get_db)) -> DataResponse:
    service = AccountService(db)
    try:
        account = service.set_paused(account_id, True)
    except AccountServiceError as exc:  # pragma: no cover - FastAPI converts
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    response = AccountPauseResponse(id=account.id, is_paused=account.is_paused)
    return DataResponse(data=response.model_dump())


@router.post("/{account_id}/resume", response_model=DataResponse)
def resume_account(account_id: int, db: Session = Depends(get_db)) -> DataResponse:
    service = AccountService(db)
    try:
        account = service.set_paused(account_id, False)
    except AccountServiceError as exc:  # pragma: no cover - FastAPI converts
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    response = AccountPauseResponse(id=account.id, is_paused=account.is_paused)
    return DataResponse(data=response.model_dump())
