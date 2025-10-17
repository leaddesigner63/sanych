from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import Proxy, ProxyScheme
from ..schemas.common import DataResponse

router = APIRouter(prefix="/proxies", tags=["proxies"])


@router.get("", response_model=DataResponse)
def list_proxies(db: Session = Depends(get_db)) -> DataResponse:
    proxies = db.query(Proxy).all()
    return DataResponse(
        data=[
            {
                "id": proxy.id,
                "name": proxy.name,
                "scheme": proxy.scheme.value,
                "host": proxy.host,
                "port": proxy.port,
            }
            for proxy in proxies
        ]
    )


@router.post("", response_model=DataResponse)
def create_proxy(payload: dict, db: Session = Depends(get_db)) -> DataResponse:
    proxy = Proxy(
        project_id=payload.get("project_id", 1),
        name=payload["name"],
        scheme=ProxyScheme(payload.get("scheme", ProxyScheme.HTTP.value)),
        host=payload["host"],
        port=int(payload["port"]),
    )
    db.add(proxy)
    db.commit()
    db.refresh(proxy)
    return DataResponse(data={"id": proxy.id, "name": proxy.name})
