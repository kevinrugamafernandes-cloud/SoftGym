import uuid
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.exceptions import NotFoundException
from app.models.gym import Gym
from app.repositories.gym_repository import GymRepository


class GymContext:
    """Gimnasio del usuario y su "hoy" (según SU zona horaria), cargado una sola vez por petición."""

    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._clock = clock
        self._gym: Optional[Gym] = None

    @property
    def gym(self) -> Gym:
        if self._gym is None:
            gym = GymRepository(self._db).get(self._gym_id)
            if gym is None:
                raise NotFoundException("Gimnasio", code="gym_not_found")
            self._gym = gym
        return self._gym

    @property
    def today(self) -> date:
        return self._clock.today(self.gym.timezone)
