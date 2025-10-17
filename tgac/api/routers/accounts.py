from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Account, AccountStatus
from ..schemas.common import DataResponse

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
