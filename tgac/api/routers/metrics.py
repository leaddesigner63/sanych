from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas.common import DataResponse
from ..services.metrics import MetricsService, MetricsServiceError

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/project/{project_id}", response_model=DataResponse)
def project_metrics(project_id: int, db: Session = Depends(get_db)) -> DataResponse:
    service = MetricsService(db)
    try:
        metrics = service.collect_project_metrics(project_id)
    except MetricsServiceError as exc:  # pragma: no cover - FastAPI handles conversion
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return DataResponse(data=[metric.as_dict() for metric in metrics])


__all__ = ["router"]
