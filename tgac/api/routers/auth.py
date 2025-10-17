from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..schemas.common import DataResponse
from ..services.auth_flow import AuthService, login_token_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram/token", response_model=DataResponse)
def create_login_token(service: AuthService = Depends(AuthService)) -> DataResponse:
    token = service.create_login_token()
    return login_token_response(token)


@router.get("/telegram/poll", response_model=DataResponse)
def poll_login_token(token: str, service: AuthService = Depends(AuthService)) -> DataResponse:
    login_token = service.validate_token(token)
    return login_token_response(login_token)


@router.post("/telegram/exchange", response_model=DataResponse)
def exchange_login_token(payload: dict, response: Response, service: AuthService = Depends(AuthService)) -> DataResponse:
    token = payload.get("login_token")
    username = payload.get("username")
    chat_id = payload.get("chat_id")
    if not token or not username or not chat_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="login_token, username and chat_id are required")
    login_token = service.confirm_token(token, username=username, chat_id=int(chat_id))
    user = service.find_or_create_user(username=username)
    cookie = service.issue_session(user)
    response.set_cookie("tgac_session", cookie, httponly=True, samesite="lax")
    return login_token_response(login_token)


@router.post("/logout", response_model=DataResponse)
def logout(response: Response) -> DataResponse:
    response.delete_cookie("tgac_session")
    return DataResponse(data={"message": "logged out"})
