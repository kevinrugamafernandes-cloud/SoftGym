import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.dependencies.auth import AdminUser, CurrentUser, DbSession, security
from app.schemas.auth import (
    LoginRequest, PasswordChange, PasswordReset, RegisterRequest, TokenResponse, UserListOut, UserOut, UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticación"])
users_router = APIRouter(prefix="/users", tags=["Usuarios"])


def _get_service(db: DbSession) -> AuthService:
    return AuthService(db)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión y recibir un JWT")
def login(payload: LoginRequest, request: Request, db: DbSession):
    # Las excepciones de dominio las convierte el manejador global (401 / 429).
    return _get_service(db).login(payload, _client_ip(request))


@router.post("/refresh", response_model=TokenResponse, summary="Renovar el token de la sesión activa")
def refresh(
    user: CurrentUser, db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    claims = decode_access_token(credentials.credentials) or {}
    return _get_service(db).refresh(user, claims)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una cuenta nueva (solo administradores)",
)
def register(payload: RegisterRequest, db: DbSession, _admin: AdminUser):
    # La cuenta nueva pertenece al gimnasio del administrador que la crea.
    return _get_service(db).register(payload, _admin.gym_id)


@router.get("/me", response_model=UserOut, summary="Usuario autenticado actual")
def me(current_user: CurrentUser):
    return current_user


@router.post("/me/password", response_model=TokenResponse, summary="Cambiar mi contraseña (cierra mis otras sesiones)")
def change_my_password(data: PasswordChange, user: CurrentUser, db: DbSession):
    return _get_service(db).change_own_password(user, data)


# ── Gestión de usuarios (administrador) ──────────────────────────────────────
@users_router.get("", response_model=UserListOut, summary="Usuarios del gimnasio")
def list_users(admin: AdminUser, db: DbSession):
    return _get_service(db).list_users(admin.gym_id)


@users_router.patch("/{user_id}", response_model=UserOut, summary="Editar nombre, rol o activar/desactivar una cuenta")
def update_user(user_id: uuid.UUID, data: UserUpdate, admin: AdminUser, db: DbSession):
    return _get_service(db).update_user(user_id, data, admin)


@users_router.post("/{user_id}/password", response_model=UserOut, summary="Asignar una contraseña nueva a una cuenta")
def reset_password(user_id: uuid.UUID, data: PasswordReset, admin: AdminUser, db: DbSession):
    return _get_service(db).reset_password(user_id, data.new_password, admin)
