import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.models.membership import Membership
from app.models.payment import Payment, PaymentMethod
from app.models.receipt_sequence import ReceiptSequence


@dataclass
class PaymentFilters:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    method: Optional[PaymentMethod] = None
    member_id: Optional[uuid.UUID] = None
    include_voided: bool = True


@dataclass
class PaymentTotals:
    active_count: int
    active_total: Decimal
    voided_count: int
    voided_total: Decimal


class PaymentRepository:
    """Acceso a datos de Payment. No hace commit: lo hace el servicio."""

    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def _loaded(self):
        return (
            selectinload(Payment.membership).selectinload(Membership.member),
            selectinload(Payment.membership).selectinload(Membership.plan),
            selectinload(Payment.registered_by),
            selectinload(Payment.voided_by),
        )

    def get(self, payment_id: uuid.UUID) -> Optional[Payment]:
        return self._db.scalars(
            select(Payment).where(Payment.gym_id == self._gym_id, Payment.id == payment_id).options(*self._loaded())
        ).first()

    def add(self, payment: Payment) -> Payment:
        self._db.add(payment)
        self._db.flush()
        return payment

    def next_receipt_number(self) -> int:
        """
        Siguiente número de comprobante del gimnasio: consecutivo y sin saltos.
        El UPDATE … RETURNING bloquea la fila del contador hasta el commit, así que dos cobros
        simultáneos se serializan y nunca reciben el mismo número; si el cobro se revierte, el
        número también (no quedan huecos).
        """
        self._db.execute(
            pg_insert(ReceiptSequence).values(gym_id=self._gym_id, last_number=0).on_conflict_do_nothing()
        )
        return self._db.execute(
            update(ReceiptSequence)
            .where(ReceiptSequence.gym_id == self._gym_id)
            .values(last_number=ReceiptSequence.last_number + 1)
            .returning(ReceiptSequence.last_number)
        ).scalar_one()

    def find_recent_duplicate(
        self, member_id: uuid.UUID, plan_id: uuid.UUID, amount: Decimal, within_seconds: int = 60
    ) -> Optional[Payment]:
        """Pago idéntico (mismo socio, plan y monto) registrado hace instantes: probable doble clic."""
        return self._db.scalars(
            select(Payment)
            .join(Membership, Membership.id == Payment.membership_id)
            .where(
                Payment.gym_id == self._gym_id,
                Membership.member_id == member_id,
                Membership.plan_id == plan_id,
                Payment.amount == amount,
                Payment.voided_at.is_(None),
                Payment.created_at >= func.now() - timedelta(seconds=within_seconds),
            )
            .limit(1)
        ).first()

    def latest_active_for_member(self, member_id: uuid.UUID) -> Optional[Payment]:
        """Último pago NO anulado del socio (el único que se puede anular)."""
        return self._db.scalars(
            select(Payment)
            .join(Membership, Membership.id == Payment.membership_id)
            .where(Payment.gym_id == self._gym_id, Membership.member_id == member_id, Payment.voided_at.is_(None))
            .order_by(Membership.end_date.desc(), Payment.receipt_number.desc())
            .limit(1)
        ).first()

    def _filtered(self, f: PaymentFilters):
        stmt = select(Payment).join(Membership, Membership.id == Payment.membership_id).where(Payment.gym_id == self._gym_id)
        if f.date_from:
            stmt = stmt.where(Payment.payment_date >= f.date_from)
        if f.date_to:
            stmt = stmt.where(Payment.payment_date <= f.date_to)
        if f.method:
            stmt = stmt.where(Payment.method == f.method)
        if f.member_id:
            stmt = stmt.where(Membership.member_id == f.member_id)
        if not f.include_voided:
            stmt = stmt.where(Payment.voided_at.is_(None))
        return stmt

    def search(self, f: PaymentFilters, *, page: int, size: int) -> Tuple[List[Payment], int]:
        base = self._filtered(f)
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = self._db.scalars(
            base.order_by(Payment.payment_date.desc(), Payment.receipt_number.desc())
            .options(*self._loaded())
            .offset((page - 1) * size)
            .limit(size)
        ).all()
        return list(items), total

    def totals(self, f: PaymentFilters) -> PaymentTotals:
        sub = self._filtered(PaymentFilters(f.date_from, f.date_to, f.method, f.member_id, True)).subquery()
        voided = sub.c.voided_at.is_not(None)
        row = self._db.execute(
            select(
                func.count().filter(~voided),
                func.coalesce(func.sum(sub.c.amount).filter(~voided), 0),
                func.count().filter(voided),
                func.coalesce(func.sum(sub.c.amount).filter(voided), 0),
            )
        ).one()
        return PaymentTotals(int(row[0]), Decimal(row[1]), int(row[2]), Decimal(row[3]))

    def cash_by_method(self, day: date) -> List[Tuple[PaymentMethod, int, Decimal]]:
        """Cobros NO anulados del día, por método de pago."""
        rows = self._db.execute(
            select(Payment.method, func.count(), func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.gym_id == self._gym_id, Payment.payment_date == day, Payment.voided_at.is_(None))
            .group_by(Payment.method)
            .order_by(Payment.method)
        ).all()
        return [(m, int(c), Decimal(t)) for m, c, t in rows]

    def voided_on(self, day: date) -> Tuple[int, Decimal]:
        row = self._db.execute(
            select(func.count(), func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.gym_id == self._gym_id, Payment.payment_date == day, Payment.voided_at.is_not(None)
            )
        ).one()
        return int(row[0]), Decimal(row[1])
