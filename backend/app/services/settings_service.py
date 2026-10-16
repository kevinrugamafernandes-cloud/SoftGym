import uuid

from sqlalchemy.orm import Session

from app.core.defaults import (
    DEFAULT_EXPIRING_MESSAGE, DEFAULT_OVERDUE_MESSAGE, MESSAGE_PLACEHOLDERS,
)
from app.core.exceptions import NotFoundException
from app.models.gym import Gym
from app.repositories.gym_repository import GymRepository
from app.schemas.settings import GymSettingsOut, GymSettingsUpdate


def settings_out(g: Gym) -> GymSettingsOut:
    return GymSettingsOut(
        name=g.name, legal_name=g.legal_name, tax_id=g.tax_id, whatsapp_phone=g.whatsapp_phone, email=g.email,
        address=g.address, receipt_message=g.receipt_message,
        overdue_message=g.overdue_message or DEFAULT_OVERDUE_MESSAGE,
        expiring_message=g.expiring_message or DEFAULT_EXPIRING_MESSAGE,
        currency=g.currency, timezone=g.timezone, placeholders=MESSAGE_PLACEHOLDERS,
    )


class SettingsService:
    """Datos del negocio del gimnasio del usuario (nombre, contacto, mensajes)."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def _gym(self) -> Gym:
        gym = GymRepository(self._db).get(self._gym_id)
        if gym is None:
            raise NotFoundException("Gimnasio", code="gym_not_found")
        return gym

    def get(self) -> GymSettingsOut:
        return settings_out(self._gym())

    def update(self, data: GymSettingsUpdate) -> GymSettingsOut:
        gym = self._gym()
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] is None:
            changes.pop("name")                       # el nombre es obligatorio: null se ignora
        for field, value in changes.items():
            setattr(gym, field, value)
        self._db.commit()
        self._db.refresh(gym)
        return settings_out(gym)
