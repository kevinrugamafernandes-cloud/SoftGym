from fastapi import APIRouter, status

from app.dependencies.auth import AdminUser, CurrentUser, DbSession
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _get_service(db: DbSession) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión y recibir un JWT")
def login(payload: LoginRequest, db: DbSession):
    # Las excepciones de dominio las convierte el manejador global (401).
    return _get_service(db).login(payload)


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
