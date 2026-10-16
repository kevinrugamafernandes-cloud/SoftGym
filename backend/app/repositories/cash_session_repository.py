import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.cash_session import CashSession, CashSessionStatus
from app.models.payment import Payment, PaymentMethod
from app.models.sale import Sale


@dataclass
class CashSessionFilters:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    cashier_id: Optional[uuid.UUID] = None
    status: Optional[CashSessionStatus] = None


@dataclass
class MethodTotals:
    payments_count: int = 0
    payments_total: Decimal = Decimal("0")
    sales_count: int = 0
    sales_total: Decimal = Decimal("0")
    sales_tax: Decimal = Decimal("0")


class CashSessionRepository:
    """Acceso a datos de CashSession. No hace commit: lo hace el servicio."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def _opts(self):
        return (selectinload(CashSession.cashier), selectinload(CashSession.closed_by))

    def get(self, session_id: uuid.UUID, *, for_update: bool = False) -> Optional[CashSession]:
        stmt = select(CashSession).where(CashSession.gym_id == self._gym_id, CashSession.id == session_id)
        stmt = stmt.with_for_update() if for_update else stmt.options(*self._opts())
        return self._db.scalars(stmt).first()

    def open_for(self, cashier_id: uuid.UUID, *, for_update: bool = False) -> Optional[CashSession]:
        """
        Caja abierta del cajero. Con for_update la fila queda BLOQUEADA hasta el commit: un cobro
        y un cierre simultáneos se serializan, y si el cierre gana, el cobro ya no la encuentra
        abierta (PostgreSQL reevalúa el WHERE tras la espera).
        """
        stmt = select(CashSession).where(
            CashSession.gym_id == self._gym_id,
            CashSession.cashier_id == cashier_id,
            CashSession.status == CashSessionStatus.OPEN,
        )
        stmt = stmt.with_for_update() if for_update else stmt.options(*self._opts())
        return self._db.scalars(stmt).first()

    def add(self, session: CashSession) -> CashSession:
        self._db.add(session)
        self._db.flush()
        return session

    def search(self, f: CashSessionFilters, *, page: int, size: int) -> Tuple[List[CashSession], int]:
        stmt = select(CashSession).where(CashSession.gym_id == self._gym_id)
        if f.date_from:
            stmt = stmt.where(CashSession.business_date >= f.date_from)
        if f.date_to:
            stmt = stmt.where(CashSession.business_date <= f.date_to)
        if f.cashier_id:
            stmt = stmt.where(CashSession.cashier_id == f.cashier_id)
        if f.status:
            stmt = stmt.where(CashSession.status == f.status)
        total = self._db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self._db.scalars(
            stmt.options(*self._opts()).order_by(CashSession.opened_at.desc()).offset((page - 1) * size).limit(size)
        ).all()
        return list(items), total

    # ── Totales del turno ─────────────────────────────────────────────────────
    def totals_by_method(self, session_id: uuid.UUID) -> Dict[PaymentMethod, MethodTotals]:
        """Cobros y ventas NO anulados del turno, por método de pago."""
        out: Dict[PaymentMethod, MethodTotals] = {}
        for method, count, total in self._db.execute(
            select(Payment.method, func.count(), func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.gym_id == self._gym_id, Payment.cash_session_id == session_id, Payment.voided_at.is_(None))
            .group_by(Payment.method)
        ).all():
            t = out.setdefault(method, MethodTotals())
            t.payments_count, t.payments_total = int(count), Decimal(total)
        for method, count, total, tax in self._db.execute(
            select(Sale.method, func.count(), func.coalesce(func.sum(Sale.total), 0), func.coalesce(func.sum(Sale.tax_total), 0))
            .where(Sale.gym_id == self._gym_id, Sale.cash_session_id == session_id, Sale.voided_at.is_(None))
            .group_by(Sale.method)
        ).all():
            t = out.setdefault(method, MethodTotals())
            t.sales_count, t.sales_total, t.sales_tax = int(count), Decimal(total), Decimal(tax)
        return out

    def voided_in(self, session_id: uuid.UUID) -> Tuple[int, Decimal]:
        p = self._db.execute(
            select(func.count(), func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.gym_id == self._gym_id, Payment.cash_session_id == session_id, Payment.voided_at.is_not(None)
            )
        ).one()
        s = self._db.execute(
            select(func.count(), func.coalesce(func.sum(Sale.total), 0)).where(
                Sale.gym_id == self._gym_id, Sale.cash_session_id == session_id, Sale.voided_at.is_not(None)
            )
        ).one()
        return int(p[0]) + int(s[0]), Decimal(p[1]) + Decimal(s[1])
