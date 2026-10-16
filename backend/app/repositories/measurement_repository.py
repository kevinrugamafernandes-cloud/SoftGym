import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.body_measurement import BodyMeasurement


class MeasurementRepository:
    """Acceso a datos de BodyMeasurement. No hace commit: lo hace el servicio."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def get(self, member_id: uuid.UUID, measurement_id: uuid.UUID) -> Optional[BodyMeasurement]:
        """Solo devuelve la medición si pertenece a ese socio (evita acceso cruzado por ID)."""
        stmt = select(BodyMeasurement).where(
            BodyMeasurement.gym_id == self._gym_id,
            BodyMeasurement.id == measurement_id,
            BodyMeasurement.member_id == member_id,
        )
        return self._db.scalars(stmt).first()

    def list_for_member(
        self, member_id: uuid.UUID, *, limit: int, offset: int
    ) -> Tuple[List[BodyMeasurement], int]:
        base = select(BodyMeasurement).where(
            BodyMeasurement.gym_id == self._gym_id, BodyMeasurement.member_id == member_id
        )
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = self._db.scalars(
            base.order_by(BodyMeasurement.recorded_at.desc(), BodyMeasurement.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(items), total

    def add(self, measurement: BodyMeasurement) -> BodyMeasurement:
        self._db.add(measurement)
        self._db.flush()
        return measurement

    def delete(self, measurement: BodyMeasurement) -> None:
        self._db.delete(measurement)
        self._db.flush()

    def flush(self) -> None:
        self._db.flush()
