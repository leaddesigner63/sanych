from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..deps import get_db
from ..services.export import ExportService, ExportServiceError

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/project/{project_id}")
def export_project(project_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    service = ExportService(db)
    try:
        payload = service.build_project_archive(project_id)
    except ExportServiceError as exc:  # pragma: no cover - FastAPI handles HTTP conversion
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    filename = f"project_{project_id}_export.zip"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
