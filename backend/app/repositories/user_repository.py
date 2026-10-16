# app/repositories/user_repository.py
import uuid
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def _norm(email: str) -> str:
    return email.strip().lower()


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id) -> Optional[User]:
        return self._db.query(User).filter(User.id == user_id).first()

    # Las búsquedas ignoran mayúsculas: "Kevin@X.com" y "kevin@x.com" son la misma
    # cuenta, y también encuentran correos antiguos guardados con mayúsculas.
    def get_by_email(self, email: str) -> Optional[User]:
        return self._db.query(User).filter(func.lower(User.email) == _norm(email)).first()

    def exists_by_email(self, email: str) -> bool:
        return self._db.query(User).filter(func.lower(User.email) == _norm(email)).count() > 0

    def create(self, full_name: str, email: str, password_hash: str, role: UserRole, gym_id: uuid.UUID) -> User:
        user = User(
            gym_id=gym_id,
            full_name=full_name,
            email=_norm(email),  # las cuentas nuevas se guardan siempre en minúsculas
            password_hash=password_hash,
            role=role,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user
