"""
Motor de morosidad: recalcula el estado de TODOS los socios según el vencimiento de su última membresía.

Se ejecuta una vez al día (CLI `python -m app.jobs.refresh_statuses`, o `POST /system/refresh-statuses`)
y es idempotente. Además, cada cobro o anulación recalcula al instante el estado de ese socio.

Reglas:
  * Solo transiciona entre activo / por vencer / moroso a socios que TIENEN al menos una membresía.
  * Un socio `inactivo` (a mano) o dado de baja NO se toca.
  * Un socio que nunca ha pagado queda como está.
  * Las membresías `activa` con vencimiento pasado pasan a `vencida`.
"""
import threading
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List

from sqlalchemy import case, cast, func, select, update
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import settings
from app.models.enums import MemberStatus
from app.models.gym import Gym
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.repositories.gym_repository import GymRepository


# Último día (del gimnasio) en que este proceso recalculó los estados: así el panel y el listado
# de socios están al día aunque el job programado no se haya ejecutado.
_refreshed_on: Dict[uuid.UUID, date] = {}
_refresh_lock = threading.Lock()


def reset_refresh_cache() -> None:
    """Solo para pruebas."""
    with _refresh_lock:
        _refreshed_on.clear()


@dataclass
class RefreshResult:
    gym_id: uuid.UUID
    memberships_expired: int
    members_updated: int


class StatusRefreshService:
    def __init__(self, db: Session, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def refresh_gym(self, gym: Gym) -> RefreshResult:
        today = self._clock.today(gym.timezone)
        warn, grace = settings.MEMBERSHIP_EXPIRING_DAYS, settings.MEMBERSHIP_GRACE_DAYS

        expired = self._db.execute(
            update(Membership)
            .where(Membership.gym_id == gym.id, Membership.status == MembershipStatus.ACTIVE, Membership.end_date < today)
            .values(status=MembershipStatus.EXPIRED)
        ).rowcount

        last = (
            select(Membership.member_id.label("member_id"), func.max(Membership.end_date).label("end_date"))
            .where(Membership.gym_id == gym.id, Membership.status != MembershipStatus.CANCELLED)
            .group_by(Membership.member_id)
            .subquery()
        )
        # El CASE devuelve texto; PostgreSQL no compara un ENUM con text, así que se castea al tipo enum.
        new_status = cast(
            case(
                (last.c.end_date < today - timedelta(days=grace), MemberStatus.EXPIRED.value),
                (last.c.end_date <= today + timedelta(days=warn), MemberStatus.EXPIRING_SOON.value),
                else_=MemberStatus.ACTIVE.value,
            ),
            Member.status.type,
        )
        updated = self._db.execute(
            update(Member)
            .where(
                Member.id == last.c.member_id,
                Member.gym_id == gym.id,
                Member.is_deleted.is_(False),
                Member.status != MemberStatus.INACTIVE,
                Member.status != new_status,
            )
            .values(status=new_status)
        ).rowcount
        self._db.commit()
        with _refresh_lock:
            _refreshed_on[gym.id] = today
        return RefreshResult(gym_id=gym.id, memberships_expired=int(expired), members_updated=int(updated))

    def ensure_fresh(self, gym: Gym) -> None:
        """Recalcula una vez por día y por proceso (barato después de la primera llamada del día)."""
        today = self._clock.today(gym.timezone)
        with _refresh_lock:
            if _refreshed_on.get(gym.id) == today:
                return
            _refreshed_on[gym.id] = today
        try:
            self.refresh_gym(gym)
        except Exception:
            with _refresh_lock:
                _refreshed_on.pop(gym.id, None)   # se reintenta en la próxima petición
            raise

    def refresh_all(self) -> List[RefreshResult]:
        return [self.refresh_gym(g) for g in GymRepository(self._db).list_active()]
