from cryptography.fernet import Fernet

from .settings import get_settings


def get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.session_secret_key.encode())


def encrypt_session(data: bytes) -> bytes:
    return get_fernet().encrypt(data)


def decrypt_session(token: bytes) -> bytes:
    return get_fernet().decrypt(token)
