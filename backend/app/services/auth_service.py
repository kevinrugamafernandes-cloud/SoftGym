# app/services/auth_service.py
import uuid

from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import ConflictException, UnauthorizedException
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: Session) -> None:
        self._repo = UserRepository(db)

    def register(self, payload: RegisterRequest, gym_id: uuid.UUID) -> User:
        if self._repo.exists_by_email(payload.email):
            raise ConflictException(
                f"Ya existe un usuario con el correo '{payload.email}'", code="user_exists"
            )

        return self._repo.create(
            full_name=payload.full_name,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            gym_id=gym_id,
        )

    def login(self, payload: LoginRequest) -> TokenResponse:
        user = self._repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedException("Correo o contraseña incorrectos", code="invalid_credentials")
        if not user.is_active:
            raise UnauthorizedException("La cuenta está deshabilitada", code="account_disabled")

        token = create_access_token(subject=str(user.id))
        return TokenResponse(access_token=token)

    def get_user_by_id(self, user_id) -> User:
        user = self._repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException("Usuario no encontrado", code="user_not_found")
        return user