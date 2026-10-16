"""Métricas del día para el panel principal (una sola petición)."""
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.clock import Clock
from app.models.cash_session import CashSession, CashSessionStatus
from app.models.enums import MemberStatus
from app.models.member import Member
from app.models.payment import Payment
from app.models.sale import Sale
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.dashboard import DashboardOut, OpenSessionOut
from app.services.cash_session_service import CashSessionService
from app.services.gym_context import GymContext
from app.services.payment_service import PaymentService


class DashboardService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._clock = clock
        self._ctx = GymContext(db, gym_id, clock)

    def summary(self, user: User) -> DashboardOut:
        today = self._ctx.today
        first = today.replace(day=1)
        day = PaymentService(self._db, self._gym_id, self._clock).cash_summary(today)

        p_month = self._db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.gym_id == self._gym_id, Payment.voided_at.is_(None),
                Payment.payment_date >= first, Payment.payment_date <= today,
            )
        )
        s_month = self._db.execute(
            select(func.coalesce(func.sum(Sale.total), 0), func.coalesce(func.sum(Sale.tax_total), 0)).where(
                Sale.gym_id == self._gym_id, Sale.voided_at.is_(None), Sale.sale_date >= first, Sale.sale_date <= today,
            )
        ).one()
        # IVA de membresías del mes: precio con IVA incluido a la tarifa guardada en cada pago.
        p_tax = self._db.scalar(
            select(func.coalesce(func.sum(Payment.amount - func.round(Payment.amount / (1 + Payment.tax_rate / 100), 2)), 0)).where(
                Payment.gym_id == self._gym_id, Payment.voided_at.is_(None),
                Payment.payment_date >= first, Payment.payment_date <= today,
            )
        )

        counts = dict(self._db.execute(
            select(Member.status, func.count()).where(Member.gym_id == self._gym_id, Member.is_deleted.is_(False))
            .group_by(Member.status)
        ).all())
        new_month = self._db.scalar(
            select(func.count()).select_from(Member).where(
                Member.gym_id == self._gym_id, Member.is_deleted.is_(False), Member.joined_at >= first,
            )
        ) or 0

        sessions = CashSessionService(self._db, self._gym_id, self._clock)
        open_rows = self._db.scalars(
            select(CashSession).options(selectinload(CashSession.cashier)).where(
                CashSession.gym_id == self._gym_id, CashSession.status == CashSessionStatus.OPEN,
            ).order_by(CashSession.opened_at)
        ).all()
        open_sessions = [
            OpenSessionOut(
                cashier_name=s.cashier.full_name,
                opened_at=s.opened_at.isoformat(),
                expected_cash=sessions._summary(s).expected_cash,   # noqa: SLF001 (mismo cálculo del arqueo)
            )
            for s in open_rows
            # La recepcionista solo ve su propio turno; el administrador ve todos.
            if user.role.value == "admin" or s.cashier_id == user.id
        ]
        cashier_roles = {"admin", "receptionist"}
        return DashboardOut(
            date=today, currency=self._ctx.gym.currency,
            today_total=day.total, today_memberships=day.payments_total, today_store=day.sales_total,
            today_payments_count=day.payments_count, today_sales_count=day.sales_count,
            month_total=Decimal(p_month) + Decimal(s_month[0]), month_tax=Decimal(p_tax) + Decimal(s_month[1]),
            members_active=counts.get(MemberStatus.ACTIVE, 0), members_expiring=counts.get(MemberStatus.EXPIRING_SOON, 0),
            members_overdue=counts.get(MemberStatus.EXPIRED, 0), members_inactive=counts.get(MemberStatus.INACTIVE, 0),
            members_new_month=new_month,
            low_stock_count=ProductRepository(self._db, self._gym_id).low_stock_count(),
            open_sessions=open_sessions,
            my_session_open=any(s.cashier_id == user.id for s in open_rows) if user.role.value in cashier_roles else None,
        )
