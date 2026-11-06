"""
Cuenta de administrador inicial (la del desarrollador), creada al arrancar la API.

Se activa con BOOTSTRAP_ADMIN_EMAIL y BOOTSTRAP_ADMIN_PASSWORD (backend/.env o variables
del servidor; nunca en el repositorio). Es idempotente y conservadora:
  * si la cuenta ya existe, NO la toca (ni su contraseña, ni su rol, ni si está activa);
  * se crea en el gimnasio activo más antiguo (el que crea la migración 0005);
  * si la base aún no está migrada o no responde, registra un aviso y la API arranca igual.
"""
import logging
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictException
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.scripts.create_admin import create_admin

logger = logging.getLogger(__name__)


def ensure_bootstrap_admin(db: Session) -> Optional[User]:
    email, password = settings.BOOTSTRAP_ADMIN_EMAIL, settings.BOOTSTRAP_ADMIN_PASSWORD
    if not email or not password:
        return None
    existing = UserRepository(db).get_by_email(email)
    if existing is not None:
        return existing
    try:
        user = create_admin(db, email=email, full_name=settings.BOOTSTRAP_ADMIN_NAME, password=password)
    except ValidationError as exc:
        logger.error("BOOTSTRAP_ADMIN inválido: %s", "; ".join(e["msg"] for e in exc.errors()))
        return None
    except ConflictException as exc:
        logger.warning("No se creó el administrador inicial: %s", exc.detail)
        return None
    logger.info("Administrador inicial creado: %s", user.email)
    return user


def run_bootstrap() -> None:
    """Punto de entrada del arranque: nunca tumba la API."""
    if not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return
    from app.db.session import SessionLocal  # import tardío: requiere DATABASE_URL

    try:
        with SessionLocal() as db:
            ensure_bootstrap_admin(db)
    except Exception:  # BD caída o sin migrar: se reintenta en el próximo arranque
        logger.exception("No se pudo verificar el administrador inicial")
