"""
Crea una cuenta de administrador desde la línea de comandos.

`POST /auth/register` ahora exige un administrador autenticado, así que la
PRIMERA cuenta de un despliegue nuevo se crea con este script:

    docker compose exec backend python -m app.scripts.create_admin \\
        --email admin@lionfitness.com --name "Administrador Lion"

La contraseña se pide de forma interactiva (no queda en el historial del shell).
También se puede pasar por la variable de entorno ADMIN_PASSWORD (CI/automatización).
"""
import argparse
import getpass
import os
import sys
import uuid
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.gym_repository import GymRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest


def create_admin(
    db: Session, *, email: str, full_name: str, password: str, gym_id: Optional[uuid.UUID] = None
) -> User:
    """Crea un admin validando correo/contraseña con las mismas reglas de la API.

    `gym_id`: gimnasio al que pertenece; por defecto, el gimnasio activo más antiguo
    (la migración 0005 crea "Lion Fitness Center").
    """
    payload = RegisterRequest(
        full_name=full_name, email=email, password=password, role=UserRole.ADMIN
    )
    if gym_id is None:
        gym = GymRepository(db).first_active()
        if gym is None:
            raise ConflictException("No hay ningún gimnasio activo. Ejecute 'alembic upgrade head' primero.")
        gym_id = gym.id
    repo = UserRepository(db)
    if repo.exists_by_email(payload.email):
        raise ConflictException(f"Ya existe un usuario con el correo '{payload.email}'")
    return repo.create(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN,
        gym_id=gym_id,
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Crear una cuenta de administrador de SoftGym")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"), required=not os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--name", default=os.getenv("ADMIN_NAME", "Administrador"))
    args = parser.parse_args(argv)

    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Contraseña (mínimo 8 caracteres): ")
    if not os.getenv("ADMIN_PASSWORD") and password != getpass.getpass("Repita la contraseña: "):
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 1

    from app.db.session import SessionLocal  # import tardío: requiere DATABASE_URL

    with SessionLocal() as db:
        try:
            user = create_admin(db, email=args.email, full_name=args.name, password=password)
        except ValidationError as exc:
            print("Datos inválidos: " + "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors()), file=sys.stderr)
            return 1
        except ConflictException as exc:
            print(exc.detail, file=sys.stderr)
            return 1
    print(f"Administrador creado: {user.email} (id {user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
