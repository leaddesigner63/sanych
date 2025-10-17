from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, status
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.core import LoginToken, LoginTokenStatus, User, UserRole
from ..schemas.common import DataResponse
from ..utils.time import utcnow
from ..utils.settings import get_settings


class AuthService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
        self.settings = get_settings()
        self.serializer = URLSafeSerializer(self.settings.session_secret_key, salt="tgac-login")

    def create_login_token(self) -> LoginToken:
        token = secrets.token_urlsafe(16)
        login_token = LoginToken(token=token)
        self.db.add(login_token)
        self.db.commit()
        return login_token

    def validate_token(self, token: str) -> LoginToken:
        login_token = self.db.get(LoginToken, token)
        if not login_token:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        ttl = timedelta(minutes=self.settings.telegram_deeplink_ttl_min)
        if login_token.status == LoginTokenStatus.CONFIRMED:
            return login_token
        if utcnow() - login_token.created_at > ttl:
            login_token.status = LoginTokenStatus.EXPIRED
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Token expired")
        return login_token

    def confirm_token(self, token: str, username: str, chat_id: int) -> LoginToken:
        login_token = self.validate_token(token)
        login_token.status = LoginTokenStatus.CONFIRMED
        login_token.username = username
        login_token.chat_id = chat_id
        login_token.confirmed_at = utcnow()
        self.db.commit()
        return login_token

    def issue_session(self, user: User) -> str:
        return self.serializer.dumps({"user_id": user.id, "role": user.role.value})

    def read_session(self, cookie: str) -> dict:
        try:
            return self.serializer.loads(cookie)
        except BadSignature as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc

    def find_or_create_user(self, username: str) -> User:
        user = self.db.query(User).filter(User.username == username).one_or_none()
        if user:
            return user
        if username != self.settings.admin_tg_username:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not allowed")
        user = User(username=username, role=UserRole.ADMIN)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


def login_token_response(token: LoginToken) -> DataResponse:
    return DataResponse(data={"login_token": token.token, "status": token.status.value})
