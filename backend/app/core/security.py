import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

from app.core.config import settings

# bcrypt solo usa los primeros 72 bytes de la contraseña (y bcrypt>=5 rechaza las más largas).
_BCRYPT_MAX_BYTES = 72


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(plain_password), hashed_password.encode("utf-8"))
    except ValueError:  # hash con formato inválido
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def password_version(password_hash: str) -> str:
    """Huella corta del hash: cambia al cambiar la contraseña e invalida los tokens anteriores."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:12]


def create_access_token(
    subject: str | Any, expires_delta: timedelta | None = None, *, pwv: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode: dict[str, Any] = {"exp": expire, "iat": now, "sub": str(subject)}
    if pwv:
        to_encode["pwv"] = pwv
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
