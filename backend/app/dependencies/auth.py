import uuid
from typing import Annotated, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import credentials_exception, forbidden_exception
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

security = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
        # decode_access_token devuelve None si el token es inválido o expiró.
        # Antes se llamaba payload.get() sobre None -> AttributeError -> HTTP 500.
        if payload is None:
            raise credentials_exception
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise credentials_exception
    return user


def require_roles(*allowed: UserRole) -> Callable[..., User]:
    """Fábrica de dependencias: permite solo a los roles indicados (403 al resto)."""
    allowed_set = frozenset(allowed)

    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_set:
            raise forbidden_exception
        return current_user

    return dependency


# Se conserva por compatibilidad con la Fase 1.
require_admin = require_roles(UserRole.ADMIN)

# ── Matriz de permisos ────────────────────────────────────────────────────────
#  AdminUser       : admin
#  FrontDeskUser   : admin, receptionist   (socios: crear/editar, planes: consultar)
#  StaffUser       : admin, receptionist, trainer   (consultar socios, ficha física)
# El rol "member" (socio) no accede a ningún endpoint administrativo.
require_front_desk = require_roles(UserRole.ADMIN, UserRole.RECEPTIONIST)
require_staff = require_roles(UserRole.ADMIN, UserRole.RECEPTIONIST, UserRole.TRAINER)

CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
FrontDeskUser = Annotated[User, Depends(require_front_desk)]
StaffUser = Annotated[User, Depends(require_staff)]
DbSession = Annotated[Session, Depends(get_db)]
