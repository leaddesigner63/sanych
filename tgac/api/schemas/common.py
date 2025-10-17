from pydantic import BaseModel


class APIResponse(BaseModel):
    ok: bool = True


class DataResponse(APIResponse):
    data: dict | list | None = None


class ErrorResponse(APIResponse):
    ok: bool = False
    error: str
