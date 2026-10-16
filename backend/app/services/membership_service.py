import uuid
from datetime import date
from typing import Dict, List, Sequence

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.models.gym import Gym
from app.repositories.gym_repository import GymRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.membership_repository import MembershipRepository
from app.schemas.membership import MembershipOut, MembershipSummary
from app.services.membership_status import days_remaining, describe_days, expiry_state


class MembershipService:
    """Membresías de un socio: resumen con tiempo restante e historial."""

    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._clock = clock
        self._memberships = MembershipRepository(db, gym_id)
        self._members = MemberRepository(db, gym_id)
        self._gym: Gym | None = None

    @property
    def gym(self) -> Gym:
        if self._gym is None:
            gym = GymRepository(self._db).get(self._gym_id)
            if gym is None:  # no debería ocurrir: users.gym_id es una FK obligatoria
                raise NotFoundException("Gimnasio", code="gym_not_found")
            self._gym = gym
        return self._gym

    @property
    def today(self) -> date:
        return self._clock.today(self.gym.timezone)

    def summaries_for(self, member_ids: Sequence[uuid.UUID]) -> Dict[uuid.UUID, MembershipSummary]:
        today = self.today
        warn = settings.MEMBERSHIP_EXPIRING_DAYS
        out: Dict[uuid.UUID, MembershipSummary] = {}
        for member_id, (m, plan_name) in self._memberships.latest_for_members(list(member_ids)).items():
            d = days_remaining(m.end_date, today)
            out[member_id] = MembershipSummary(
                id=m.id, plan_id=m.plan_id, plan_name=plan_name,
                start_date=m.start_date, end_date=m.end_date,
                days_remaining=d, days_overdue=max(0, -d),
                state=expiry_state(m.end_date, today, warn), label=describe_days(d),
            )
        return out

    def history(self, member_id: uuid.UUID) -> List[MembershipOut]:
        if self._members.get(member_id, include_deleted=True) is None:
            raise NotFoundException("Socio", code="member_not_found")
        return [
            MembershipOut(
                id=m.id, plan_id=m.plan_id, plan_name=name, start_date=m.start_date,
                end_date=m.end_date, status=m.status, created_at=m.created_at,
            )
            for m, name in self._memberships.history(member_id)
        ]
