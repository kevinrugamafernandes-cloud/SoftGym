import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gym import Gym


class GymRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, gym_id: uuid.UUID) -> Optional[Gym]:
        return self._db.get(Gym, gym_id)

    def get_by_slug(self, slug: str) -> Optional[Gym]:
        return self._db.scalars(select(Gym).where(Gym.slug == slug)).first()

    def first_active(self) -> Optional[Gym]:
        """Gimnasio por defecto: el más antiguo activo (en instalaciones de un solo gimnasio, el único)."""
        return self._db.scalars(select(Gym).where(Gym.is_active.is_(True)).order_by(Gym.created_at, Gym.id)).first()

    def list_active(self) -> list[Gym]:
        return list(self._db.scalars(select(Gym).where(Gym.is_active.is_(True)).order_by(Gym.created_at)).all())
