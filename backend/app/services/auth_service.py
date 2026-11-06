# app/services/auth_service.py
import time
import uuid

from sqlalchemy.orm import Session

from app.core import login_throttle
from app.core.config import settings
from app.core.exceptions import (
    BusinessRuleException, ConflictException, NotFoundException, UnauthorizedException,
)
from app.core.security import create_access_token, hash_password, password_version, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest, PasswordChange, RegisterRequest, TokenResponse, UserListOut, UserOut, UserUpdate,
)

# Hash de una contraseña cualquiera: se verifica contra él cuando el correo no existe, para que
# el tiempo de respuesta no delate qué correos están registrados.
_DUMMY_HASH = hash_password("contraseña-de-relleno")


def issue_token(user: User, session_started: int | None = None) -> TokenResponse:
    """Token de acceso. `sat` = inicio de la sesión: se conserva al renovar para limitar su duración total."""
    sat = session_started if session_started is not None else int(time.time())
    token = create_access_token(subject=str(user.id), pwv=password_version(user.password_hash), extra={"sat": sat})
    return TokenResponse(access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = UserRepository(db)

    # ── Cuentas ───────────────────────────────────────────────────────────────
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

    def list_users(self, gym_id: uuid.UUID) -> UserListOut:
        return UserListOut(items=[UserOut.model_validate(u) for u in self._repo.list_for_gym(gym_id)])

    def update_user(self, user_id: uuid.UUID, data: UserUpdate, admin: User) -> User:
        user = self._get(user_id, admin.gym_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if user.id == admin.id and (changes.get("is_active") is False or changes.get("role", UserRole.ADMIN) != UserRole.ADMIN):
            raise BusinessRuleException(
                "No puede desactivarse ni quitarse el rol de administrador a sí mismo", code="cannot_demote_self"
            )
        losing_admin = user.role == UserRole.ADMIN and user.is_active and (
            changes.get("is_active") is False or changes.get("role", UserRole.ADMIN) != UserRole.ADMIN
        )
        if losing_admin and self._repo.count_active_admins(admin.gym_id) <= 1:
            raise BusinessRuleException("El gimnasio debe conservar al menos un administrador activo", code="last_admin")
        for field, value in changes.items():
            setattr(user, field, value)
        self._db.commit()
        self._db.refresh(user)
        return user

    def reset_password(self, user_id: uuid.UUID, new_password: str, admin: User) -> User:
        user = self._get(user_id, admin.gym_id)
        user.password_hash = hash_password(new_password)   # invalida sus sesiones abiertas
        self._db.commit()
        self._db.refresh(user)
        return user

    def change_own_password(self, user: User, data: PasswordChange) -> TokenResponse:
        if not verify_password(data.current_password, user.password_hash):
            raise BusinessRuleException("La contraseña actual no es correcta", code="wrong_password")
        if data.current_password == data.new_password:
            raise BusinessRuleException("La contraseña nueva debe ser distinta de la actual", code="same_password")
        user.password_hash = hash_password(data.new_password)
        self._db.commit()
        self._db.refresh(user)
        return issue_token(user)   # las demás sesiones quedan cerradas; esta sigue con un token nuevo

    def _get(self, user_id: uuid.UUID, gym_id: uuid.UUID) -> User:
        user = self._repo.get_in_gym(user_id, gym_id)
        if user is None:
            raise NotFoundException("Usuario", code="user_not_found")
        return user

    # ── Sesión ────────────────────────────────────────────────────────────────
    def login(self, payload: LoginRequest, ip: str = "desconocida") -> TokenResponse:
        login_throttle.check(payload.email, ip)
        user = self._repo.get_by_email(payload.email)
        valid = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
        if not user or not valid:
            login_throttle.register_failure(payload.email, ip)
            raise UnauthorizedException("Correo o contraseña incorrectos", code="invalid_credentials")
        if not user.is_active:
            raise UnauthorizedException("La cuenta está deshabilitada", code="account_disabled")

        login_throttle.register_success(payload.email)
        return issue_token(user)

    def refresh(self, user: User, claims: dict) -> TokenResponse:
        """Renueva el token de una sesión activa, sin superar SESSION_MAX_HOURS desde el login."""
        started = int(claims.get("sat") or claims.get("iat") or 0)
        if time.time() - started > settings.SESSION_MAX_HOURS * 3600:
            raise UnauthorizedException("La sesión expiró. Inicie sesión de nuevo", code="session_expired")
        return issue_token(user, session_started=started)

    def get_user_by_id(self, user_id) -> User:
        user = self._repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException("Usuario no encontrado", code="user_not_found")
        return user
