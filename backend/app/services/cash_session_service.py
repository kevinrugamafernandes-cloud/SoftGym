"""
Sesiones de caja: abrir turno con fondo inicial, registrar cobros/ventas en él y cerrarlo
con arqueo (efectivo contado vs. esperado). El cierre guarda una instantánea inmutable.
"""
import math
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.exceptions import (
    BusinessRuleException, ConflictException, ForbiddenException, NotFoundException,
)
from app.models.cash_session import CashSession, CashSessionStatus
from app.models.payment import PaymentMethod
from app.models.user import User, UserRole
from app.repositories.cash_session_repository import CashSessionFilters, CashSessionRepository
from app.schemas.cash_session import (
    CashierOut, CashSessionClose, CashSessionListItemOut, CashSessionListOut, CashSessionOpen, CashSessionOut,
    CashSessionSummaryOut, CurrentCashSessionOut, SessionMethodTotalOut,
)
from app.services.gym_context import GymContext
from app.utils.money import q2

ZERO = Decimal("0.00")


def cash_session_required() -> ConflictException:
    return ConflictException(
        "No tiene una caja abierta. Abra caja con el fondo inicial antes de cobrar o vender",
        code="cash_session_required",
    )


class CashSessionService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._clock = clock
        self._repo = CashSessionRepository(db, gym_id)
        self._ctx = GymContext(db, gym_id, clock)

    # ── Uso desde cobros y ventas ─────────────────────────────────────────────
    def lock_open_for(self, user: User) -> Optional[CashSession]:
        """Caja abierta del usuario, BLOQUEADA hasta el commit (ver CashSessionRepository.open_for)."""
        return self._repo.open_for(user.id, for_update=True)

    # ── Abrir ─────────────────────────────────────────────────────────────────
    def open(self, data: CashSessionOpen, user: User) -> CashSessionOut:
        if self._repo.open_for(user.id) is not None:
            raise ConflictException("Ya tiene una caja abierta. Ciérrela antes de abrir otra", code="cash_session_already_open")
        session = CashSession(
            gym_id=self._gym_id, cashier_id=user.id, status=CashSessionStatus.OPEN,
            business_date=self._ctx.today, opened_at=self._clock.now(),
            opening_float=q2(data.opening_float), opening_notes=data.notes,
        )
        try:
            self._repo.add(session)
            self._db.commit()
        except IntegrityError:
            # Dos aperturas simultáneas: el índice único parcial deja pasar solo una.
            self._db.rollback()
            raise ConflictException("Ya tiene una caja abierta. Ciérrela antes de abrir otra", code="cash_session_already_open")
        return self._out(self._reload(session.id))

    # ── Cerrar ────────────────────────────────────────────────────────────────
    def close(self, session_id: uuid.UUID, data: CashSessionClose, user: User) -> CashSessionOut:
        try:
            return self._close(session_id, data, user)
        except Exception:
            self._db.rollback()
            raise

    def _close(self, session_id: uuid.UUID, data: CashSessionClose, user: User) -> CashSessionOut:
        session = self._repo.get(session_id, for_update=True)  # bloquea: ningún cobro entra durante el cierre
        if session is None:
            raise NotFoundException("Sesión de caja", feminine=True, code="cash_session_not_found")
        if session.cashier_id != user.id and user.role != UserRole.ADMIN:
            raise ForbiddenException("Solo el cajero que abrió la caja o un administrador puede cerrarla")
        if session.status != CashSessionStatus.OPEN:
            raise ConflictException("La caja ya está cerrada", code="cash_session_closed")

        summary = self._summary(session)
        counted = q2(data.counted_cash)
        difference = counted - summary.expected_cash
        if difference != 0 and not data.notes:
            raise BusinessRuleException(
                "Hay una diferencia en el arqueo: explique el sobrante o faltante en las observaciones",
                code="closing_notes_required",
            )

        session.status = CashSessionStatus.CLOSED
        session.closed_at = self._clock.now()
        session.closed_by_id = user.id
        session.cash_payments_total = summary.cash_payments_total
        session.cash_sales_total = summary.cash_sales_total
        session.expected_cash = summary.expected_cash
        session.counted_cash = counted
        session.difference = difference
        session.closing_notes = data.notes
        self._db.commit()
        return self._out(self._reload(session.id))

    # ── Consultas ─────────────────────────────────────────────────────────────
    def current(self, user: User) -> CurrentCashSessionOut:
        session = self._repo.open_for(user.id)
        return CurrentCashSessionOut(session=self._out(session) if session else None)

    def get(self, session_id: uuid.UUID, user: User) -> CashSessionOut:
        session = self._repo.get(session_id)
        # La recepcionista solo ve SUS turnos; uno ajeno se trata como inexistente.
        if session is None or (user.role != UserRole.ADMIN and session.cashier_id != user.id):
            raise NotFoundException("Sesión de caja", feminine=True, code="cash_session_not_found")
        return self._out(session)

    def list(self, f: CashSessionFilters, user: User, *, page: int, size: int) -> CashSessionListOut:
        if user.role != UserRole.ADMIN:
            f.cashier_id = user.id
        items, total = self._repo.search(f, page=page, size=size)
        return CashSessionListOut(
            items=[
                CashSessionListItemOut(
                    id=s.id, cashier=CashierOut(id=s.cashier.id, full_name=s.cashier.full_name), status=s.status,
                    business_date=s.business_date, opened_at=s.opened_at, closed_at=s.closed_at,
                    opening_float=s.opening_float, expected_cash=s.expected_cash, counted_cash=s.counted_cash,
                    difference=s.difference,
                )
                for s in items
            ],
            total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0,
        )

    # ── Internos ──────────────────────────────────────────────────────────────
    def _reload(self, session_id: uuid.UUID) -> CashSession:
        session = self._repo.get(session_id)
        assert session is not None
        self._db.refresh(session)
        return session

    def _summary(self, session: CashSession) -> CashSessionSummaryOut:
        by_method = self._repo.totals_by_method(session.id)
        rows = [
            SessionMethodTotalOut(
                method=m, payments_count=t.payments_count, payments_total=q2(t.payments_total),
                sales_count=t.sales_count, sales_total=q2(t.sales_total),
                total=q2(t.payments_total + t.sales_total),
            )
            for m, t in sorted(by_method.items(), key=lambda kv: list(PaymentMethod).index(kv[0]))
        ]
        cash = by_method.get(PaymentMethod.CASH)
        cash_payments = q2(cash.payments_total) if cash else ZERO
        cash_sales = q2(cash.sales_total) if cash else ZERO
        voided_count, voided_total = self._repo.voided_in(session.id)
        payments_total = q2(sum((t.payments_total for t in by_method.values()), ZERO))
        sales_total = q2(sum((t.sales_total for t in by_method.values()), ZERO))
        return CashSessionSummaryOut(
            payments_count=sum(t.payments_count for t in by_method.values()),
            payments_total=payments_total,
            sales_count=sum(t.sales_count for t in by_method.values()),
            sales_total=sales_total,
            sales_tax_total=q2(sum((t.sales_tax for t in by_method.values()), ZERO)),
            total=payments_total + sales_total,
            by_method=rows,
            cash_payments_total=cash_payments,
            cash_sales_total=cash_sales,
            expected_cash=q2(session.opening_float) + cash_payments + cash_sales,
            voided_count=voided_count,
            voided_total=q2(voided_total),
        )

    def _out(self, s: CashSession) -> CashSessionOut:
        return CashSessionOut(
            id=s.id, cashier=CashierOut(id=s.cashier.id, full_name=s.cashier.full_name), status=s.status,
            business_date=s.business_date, opened_at=s.opened_at, opening_float=s.opening_float,
            opening_notes=s.opening_notes, closed_at=s.closed_at,
            closed_by_name=s.closed_by.full_name if s.closed_by else None,
            cash_payments_total=s.cash_payments_total, cash_sales_total=s.cash_sales_total,
            expected_cash=s.expected_cash, counted_cash=s.counted_cash, difference=s.difference,
            closing_notes=s.closing_notes, currency=self._ctx.gym.currency, summary=self._summary(s),
        )
