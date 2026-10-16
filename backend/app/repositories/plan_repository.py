import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.plan import Plan


class PlanRepository:
    """Acceso a datos de Plan. No hace commit: lo hace el servicio."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def get(self, plan_id: uuid.UUID) -> Optional[Plan]:
        plan = self._db.get(Plan, plan_id)
        return plan if plan is not None and plan.gym_id == self._gym_id else None

    def get_by_name(self, name: str, *, exclude_id: Optional[uuid.UUID] = None) -> Optional[Plan]:
        """Búsqueda por nombre SIN distinguir mayúsculas ('Mensual' == 'mensual')."""
        stmt = select(Plan).where(Plan.gym_id == self._gym_id, func.lower(Plan.name) == name.strip().lower())
        if exclude_id is not None:
            stmt = stmt.where(Plan.id != exclude_id)
        return self._db.scalars(stmt).first()

    def list(self, *, active_only: bool = False) -> List[Plan]:
        stmt = select(Plan).where(Plan.gym_id == self._gym_id)
        if active_only:
            stmt = stmt.where(Plan.is_active.is_(True))
        return list(self._db.scalars(stmt.order_by(Plan.duration_days, Plan.name)).all())

    def count_memberships(self, plan_id: uuid.UUID) -> int:
        return self._db.scalar(
            select(func.count()).select_from(Membership).where(Membership.plan_id == plan_id)
        ) or 0

    def add(self, plan: Plan) -> Plan:
        self._db.add(plan)
        self._db.flush()
        return plan

    def delete(self, plan: Plan) -> None:
        self._db.delete(plan)
        self._db.flush()

    def flush(self) -> None:
        self._db.flush()
