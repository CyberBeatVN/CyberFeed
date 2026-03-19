"""Security utilities: JWT, password hashing, Fernet encryption."""

import base64
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from cyberfeed.config import get_settings

_FERNET_SALT = b"cyberfeed-config-encryption-salt"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_fernet() -> Fernet:
    """Derive a Fernet key from SECRET_KEY for encrypting sensitive config fields."""
    settings = get_settings()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_FERNET_SALT,
        iterations=480_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    return get_fernet().decrypt(encrypted.encode()).decode()
