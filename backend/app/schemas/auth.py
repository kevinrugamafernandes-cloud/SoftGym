# app/schemas/auth.py
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.user import UserRole


def _check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 caracteres")
    return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.RECEPTIONIST

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password(v)

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre completo no puede estar vacío")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0          # segundos de vida del token


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    gym_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Edición de una cuenta por el administrador (los campos omitidos no cambian)."""
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        return v.lower() if isinstance(v, str) else v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("El nombre completo no puede estar vacío")
        return v


class PasswordReset(BaseModel):
    """El administrador asigna una contraseña nueva a otra cuenta."""
    new_password: str

    _v = field_validator("new_password")(classmethod(lambda cls, v: _check_password(v)))


class PasswordChange(BaseModel):
    """El usuario cambia su propia contraseña."""
    current_password: str
    new_password: str

    _v = field_validator("new_password")(classmethod(lambda cls, v: _check_password(v)))


class UserListOut(BaseModel):
    items: List[UserOut]
