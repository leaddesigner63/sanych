from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Account, AccountStatus
from ..schemas import AssignProxyRequest
from ..schemas.common import DataResponse
from ..services.accounts import AccountService, AccountServiceError

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=DataResponse)
def list_accounts(db: Session = Depends(get_db)) -> DataResponse:
    accounts = db.query(Account).limit(100).all()
    return DataResponse(
        data=[
            {
                "id": account.id,
                "phone": account.phone,
                "status": account.status.value,
                "project_id": account.project_id,
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
