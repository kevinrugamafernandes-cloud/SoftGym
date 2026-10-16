import uuid
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.plan import Plan
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanCreate, PlanUpdate


class PlanService:
    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id
        self._repo = PlanRepository(db, gym_id)

    def list(self, *, active_only: bool = False) -> List[Plan]:
        return self._repo.list(active_only=active_only)

    def get(self, plan_id: uuid.UUID) -> Plan:
        plan = self._repo.get(plan_id)
        if plan is None:
            raise NotFoundException("Plan", code="plan_not_found")
        return plan

    def _ensure_name_free(self, name: str, *, exclude_id=None) -> None:
        if self._repo.get_by_name(name, exclude_id=exclude_id) is not None:
            raise ConflictException(f"Ya existe un plan llamado '{name}'", code="plan_name_taken")

    def create(self, data: PlanCreate) -> Plan:
        self._ensure_name_free(data.name)
        plan = Plan(gym_id=self._gym_id, **data.model_dump())
        try:
            self._repo.add(plan)
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ConflictException(f"Ya existe un plan llamado '{data.name}'", code="plan_name_taken")
        self._db.refresh(plan)
        return plan

    def update(self, plan_id: uuid.UUID, data: PlanUpdate) -> Plan:
        plan = self.get(plan_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            self._ensure_name_free(changes["name"], exclude_id=plan.id)
        for field, value in changes.items():
            setattr(plan, field, value)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ConflictException("Ya existe un plan con ese nombre", code="plan_name_taken")
        self._db.refresh(plan)
        return plan

    def delete(self, plan_id: uuid.UUID) -> None:
        plan = self.get(plan_id)
        if self._repo.count_memberships(plan.id) > 0:
            raise ConflictException(
                "No se puede eliminar el plan porque tiene membresías asociadas. "
                "Desactívelo para que deje de ofrecerse.",
                code="plan_in_use",
            )
        self._repo.delete(plan)
        self._db.commit()
