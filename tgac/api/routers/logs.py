from __future__ import annotations

from fastapi import APIRouter

from ..schemas.common import DataResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/tail", response_model=DataResponse)
def tail_logs(lines: int = 200) -> DataResponse:
    path = "tgac/logs/app.log"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.readlines()[-lines:]
    except FileNotFoundError:
        content = []
    return DataResponse(data={"lines": content})
