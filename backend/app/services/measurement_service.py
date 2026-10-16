import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleException, NotFoundException
from app.models.body_measurement import BodyMeasurement
from app.models.user import User
from app.repositories.measurement_repository import MeasurementRepository
from app.repositories.member_repository import MemberRepository
from app.schemas.body_measurement import BodyMeasurementCreate, BodyMeasurementUpdate
from app.utils.anthropometrics import calculate_bmi

_METRICS = (
    "weight_kg", "height_cm", "body_fat_pct", "muscle_pct", "chest_cm",
    "waist_cm", "hips_cm", "arms_cm", "thighs_cm", "calves_cm",
)
_CLOCK_SKEW = timedelta(minutes=5)


def _as_aware(dt: datetime) -> datetime:
    """Un datetime sin zona horaria se interpreta como UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class MeasurementService:
    """Ficha física: historial de mediciones antropométricas de un socio."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id
        self._repo = MeasurementRepository(db, gym_id)
        self._members = MemberRepository(db, gym_id)

    def _ensure_member(self, member_id: uuid.UUID) -> None:
        if self._members.get(member_id) is None:
            raise NotFoundException("Socio", code="member_not_found")

    def list(
        self, member_id: uuid.UUID, *, limit: int, offset: int
    ) -> Tuple[List[BodyMeasurement], int]:
        self._ensure_member(member_id)
        return self._repo.list_for_member(member_id, limit=limit, offset=offset)

    def get(self, member_id: uuid.UUID, measurement_id: uuid.UUID) -> BodyMeasurement:
        self._ensure_member(member_id)
        measurement = self._repo.get(member_id, measurement_id)
        if measurement is None:
            raise NotFoundException("Medición", feminine=True, code="measurement_not_found")
        return measurement

    def create(
        self, member_id: uuid.UUID, data: BodyMeasurementCreate, recorded_by: User
    ) -> BodyMeasurement:
        self._ensure_member(member_id)

        values = data.model_dump(exclude={"recorded_at"})  # incluye bmi (computed_field)
        if data.recorded_at is not None:
            recorded_at = _as_aware(data.recorded_at)
            if recorded_at > datetime.now(timezone.utc) + _CLOCK_SKEW:
                raise BusinessRuleException(
                    "La fecha de la medición no puede ser futura", code="measurement_in_future"
                )
            values["recorded_at"] = recorded_at

        measurement = BodyMeasurement(
            gym_id=self._gym_id, member_id=member_id, recorded_by_id=recorded_by.id, **values
        )
        self._repo.add(measurement)
        self._db.commit()
        self._db.refresh(measurement)
        return measurement

    def update(
        self, member_id: uuid.UUID, measurement_id: uuid.UUID, data: BodyMeasurementUpdate
    ) -> BodyMeasurement:
        measurement = self.get(member_id, measurement_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(measurement, field, value)

        # Se validan los valores FINALES (los nuevos mezclados con los ya guardados).
        if all(getattr(measurement, m) is None for m in _METRICS):
            self._db.rollback()
            raise BusinessRuleException(
                "La medición debe conservar al menos una medida", code="measurement_empty"
            )
        if (
            measurement.body_fat_pct is not None
            and measurement.muscle_pct is not None
            and measurement.body_fat_pct + measurement.muscle_pct > 100
        ):
            self._db.rollback()
            raise BusinessRuleException(
                "La suma de % grasa y % músculo no puede superar 100", code="composition_over_100"
            )

        # El IMC nunca lo envía el cliente: se recalcula siempre con peso y estatura finales.
        measurement.bmi = calculate_bmi(measurement.weight_kg, measurement.height_cm)
        self._db.commit()
        self._db.refresh(measurement)
        return measurement

    def delete(self, member_id: uuid.UUID, measurement_id: uuid.UUID) -> None:
        measurement = self.get(member_id, measurement_id)
        self._repo.delete(measurement)
        self._db.commit()
