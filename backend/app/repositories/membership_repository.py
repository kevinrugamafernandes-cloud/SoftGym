import uuid
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership, MembershipStatus
from app.models.plan import Plan


class MembershipRepository:
    """Acceso a datos de Membership. No hace commit."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def latest_for_member(self, member_id: uuid.UUID) -> Optional[Membership]:
        """Última membresía NO cancelada (la de mayor vencimiento)."""
        return self._db.scalars(
            select(Membership)
            .where(
                Membership.gym_id == self._gym_id,
                Membership.member_id == member_id,
                Membership.status != MembershipStatus.CANCELLED,
            )
            .order_by(Membership.end_date.desc(), Membership.created_at.desc())
            .limit(1)
        ).first()

    def latest_for_members(self, member_ids: Sequence[uuid.UUID]) -> Dict[uuid.UUID, Tuple[Membership, str]]:
        """Última membresía (y nombre del plan) de cada socio, en UNA sola consulta."""
        if not member_ids:
            return {}
        rows = self._db.execute(
            select(Membership, Plan.name)
            .join(Plan, Plan.id == Membership.plan_id)
            .where(
                Membership.gym_id == self._gym_id,
                Membership.member_id.in_(member_ids),
                Membership.status != MembershipStatus.CANCELLED,
            )
            .distinct(Membership.member_id)
            .order_by(Membership.member_id, Membership.end_date.desc(), Membership.created_at.desc())
        ).all()
        return {m.member_id: (m, plan_name) for m, plan_name in rows}

    def history(self, member_id: uuid.UUID) -> List[Tuple[Membership, str]]:
        rows = self._db.execute(
            select(Membership, Plan.name)
            .join(Plan, Plan.id == Membership.plan_id)
            .where(Membership.gym_id == self._gym_id, Membership.member_id == member_id)
            .order_by(Membership.start_date.desc(), Membership.created_at.desc())
        ).all()
        return [(m, name) for m, name in rows]

    def add(self, membership: Membership) -> Membership:
        self._db.add(membership)
        self._db.flush()
        return membership
