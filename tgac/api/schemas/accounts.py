"""Pydantic models related to account operations."""

from pydantic import BaseModel


class AssignProxyRequest(BaseModel):
    proxy_id: int


__all__ = ["AssignProxyRequest"]
