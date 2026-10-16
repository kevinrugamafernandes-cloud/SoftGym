"""
Cobranza: lista de socios morosos (membresía vencida) o por vencer, con el mensaje de
recordatorio ya armado (plantilla de Configuración) y su enlace wa.me.
"""
import math
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import settings
from app.core.defaults import DEFAULT_EXPIRING_MESSAGE, DEFAULT_OVERDUE_MESSAGE
from app.core.exceptions import BusinessRuleException, NotFoundException
from app.models.enums import MemberStatus
from app.models.member import Member
from app.models.member_reminder import MemberReminder
from app.models.membership import Membership, MembershipStatus
from app.models.plan import Plan
from app.models.user import User
from app.repositories.member_repository import MemberRepository, _escape_like
from app.schemas.collections import CollectionItemOut, CollectionListOut, CollectionState, ReminderOut
from app.services.gym_context import GymContext
from app.services.membership_status import describe_days
from app.utils.templates import render_template
from app.utils.whatsapp import normalize_phone, wa_link


def _days_text(d: int) -> str:
    if d == 0:
        return "hoy"
    if d == 1:
        return "mañana"
    if d > 1:
        return f"en {d} días"
    return "ayer" if d == -1 else f"hace {-d} días"


class CollectionsService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._ctx = GymContext(db, gym_id, clock)

    def _latest(self):
        """Última membresía NO cancelada de cada socio (con el nombre del plan)."""
        return (
            select(
                Membership.member_id.label("member_id"), Membership.end_date.label("end_date"),
                Plan.name.label("plan_name"),
            )
            .join(Plan, Plan.id == Membership.plan_id)
            .where(Membership.gym_id == self._gym_id, Membership.status != MembershipStatus.CANCELLED)
            .distinct(Membership.member_id)
            .order_by(Membership.member_id, Membership.end_date.desc(), Membership.created_at.desc())
            .subquery()
        )

    def list(self, state: CollectionState, *, search: Optional[str], page: int, size: int) -> CollectionListOut:
        today = self._ctx.today
        warn = settings.MEMBERSHIP_EXPIRING_DAYS
        last = self._latest()
        reminded = (
            select(MemberReminder.member_id, func.max(MemberReminder.created_at).label("at"))
            .where(MemberReminder.gym_id == self._gym_id)
            .group_by(MemberReminder.member_id)
            .subquery()
        )
        base = (
            select(Member, last.c.end_date, last.c.plan_name, reminded.c.at)
            .join(last, last.c.member_id == Member.id)
            .outerjoin(reminded, reminded.c.member_id == Member.id)
            # Un socio dado de baja o inactivado a mano no se cobra.
            .where(Member.gym_id == self._gym_id, Member.is_deleted.is_(False), Member.status != MemberStatus.INACTIVE)
        )
        overdue_cond = last.c.end_date < today
        expiring_cond = (last.c.end_date >= today) & (last.c.end_date <= today + timedelta(days=warn))
        counts = self._db.execute(
            select(
                func.count().filter(overdue_cond),
                func.count().filter(expiring_cond),
            )
            .select_from(Member)
            .join(last, last.c.member_id == Member.id)
            .where(Member.gym_id == self._gym_id, Member.is_deleted.is_(False), Member.status != MemberStatus.INACTIVE)
        ).one()

        stmt = base.where(overdue_cond if state == "vencida" else expiring_cond)
        if search and search.strip():
            for word in search.split():
                pattern = f"%{_escape_like(word)}%"
                stmt = stmt.where(or_(
                    func.unaccent(Member.first_name).ilike(func.unaccent(pattern), escape="\\"),
                    func.unaccent(Member.last_name).ilike(func.unaccent(pattern), escape="\\"),
                    Member.identification.ilike(pattern, escape="\\"),
                ))
        total = self._db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        # Vencidas: las más recientes primero (las más fáciles de recuperar). Por vencer: las más próximas.
        order = (last.c.end_date.desc(),) if state == "vencida" else (last.c.end_date.asc(),)
        rows = self._db.execute(
            stmt.order_by(*order, Member.last_name, Member.first_name).offset((page - 1) * size).limit(size)
        ).all()

        return CollectionListOut(
            items=[self._item(m, end, plan, at, state) for m, end, plan, at in rows],
            total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0,
            overdue_count=int(counts[0]), expiring_count=int(counts[1]),
        )

    def _item(self, m: Member, end_date, plan_name: str, reminded_at, state: CollectionState) -> CollectionItemOut:
        gym = self._ctx.gym
        d = (end_date - self._ctx.today).days
        template = (gym.overdue_message or DEFAULT_OVERDUE_MESSAGE) if state == "vencida" else (gym.expiring_message or DEFAULT_EXPIRING_MESSAGE)
        message = render_template(template, {
            "nombre": m.first_name.split()[0].title() if m.first_name else m.full_name,
            "gimnasio": gym.name, "plan": plan_name, "fecha_vencimiento": end_date.strftime("%d/%m/%Y"),
            "dias": _days_text(d), "telefono": gym.whatsapp_phone or "",
        })
        number = normalize_phone(m.phone)
        return CollectionItemOut(
            member_id=m.id, full_name=m.full_name, identification=m.identification, phone=m.phone,
            plan_name=plan_name, end_date=end_date, days=abs(d), state=state, label=describe_days(d),
            last_reminder_at=reminded_at, whatsapp_url=wa_link(number, message) if number else None, message=message,
        )

    def log_reminder(self, member_id: uuid.UUID, kind: CollectionState, user: User) -> ReminderOut:
        member = MemberRepository(self._db, self._gym_id).get(member_id)
        if member is None:
            raise NotFoundException("Socio", code="member_not_found")
        number = normalize_phone(member.phone)
        if number is None:
            raise BusinessRuleException("El socio no tiene un teléfono válido", code="phone_required")
        latest = self._db.scalar(
            select(func.max(Membership.end_date)).where(
                Membership.gym_id == self._gym_id, Membership.member_id == member_id,
                Membership.status != MembershipStatus.CANCELLED,
            )
        )
        r = MemberReminder(gym_id=self._gym_id, member_id=member_id, kind=kind, membership_end_date=latest,
                           phone=number, sent_by_id=user.id)
        self._db.add(r)
        self._db.commit()
        self._db.refresh(r)
        return ReminderOut(member_id=member_id, kind=kind, created_at=r.created_at)
