import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.payment import PaymentMethod
from app.models.sale import Sale


@dataclass
class SaleFilters:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    method: Optional[PaymentMethod] = None
    member_id: Optional[uuid.UUID] = None
    cash_session_id: Optional[uuid.UUID] = None
    include_voided: bool = True


@dataclass
class SaleTotals:
    active_count: int
    active_total: Decimal
    active_tax: Decimal
    voided_count: int
    voided_total: Decimal


class SaleRepository:
    def __init__(self, db: Session, gym_id: uuid.UUID) -> None:
        self._db = db
        self._gym_id = gym_id

    def _opts(self):
        return (
            selectinload(Sale.items), selectinload(Sale.cashier), selectinload(Sale.voided_by),
            selectinload(Sale.member),
        )

    def get(self, sale_id: uuid.UUID, *, for_update: bool = False) -> Optional[Sale]:
        stmt = select(Sale).where(Sale.gym_id == self._gym_id, Sale.id == sale_id)
        if for_update:
            stmt = stmt.with_for_update(of=Sale)
        return self._db.scalars(stmt.options(*self._opts())).first()

    def add(self, sale: Sale) -> Sale:
        self._db.add(sale)
        self._db.flush()
        return sale

    def codes_for(self, sale_ids: Sequence[uuid.UUID]) -> Dict[uuid.UUID, int]:
        if not sale_ids:
            return {}
        rows = self._db.execute(select(Sale.id, Sale.sale_number).where(Sale.id.in_(list(sale_ids)))).all()
        return {i: n for i, n in rows}

    def _filtered(self, f: SaleFilters):
        stmt = select(Sale).where(Sale.gym_id == self._gym_id)
        if f.date_from:
            stmt = stmt.where(Sale.sale_date >= f.date_from)
        if f.date_to:
            stmt = stmt.where(Sale.sale_date <= f.date_to)
        if f.method:
            stmt = stmt.where(Sale.method == f.method)
        if f.member_id:
            stmt = stmt.where(Sale.member_id == f.member_id)
        if f.cash_session_id:
            stmt = stmt.where(Sale.cash_session_id == f.cash_session_id)
        if not f.include_voided:
            stmt = stmt.where(Sale.voided_at.is_(None))
        return stmt

    def search(self, f: SaleFilters, *, page: int, size: int) -> Tuple[List[Sale], int]:
        base = self._filtered(f)
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = self._db.scalars(
            base.options(*self._opts()).order_by(Sale.sale_date.desc(), Sale.sale_number.desc())
            .offset((page - 1) * size).limit(size)
        ).all()
        return list(items), total

    def totals(self, f: SaleFilters) -> SaleTotals:
        sub = self._filtered(SaleFilters(f.date_from, f.date_to, f.method, f.member_id, f.cash_session_id, True)).subquery()
        voided = sub.c.voided_at.is_not(None)
        row = self._db.execute(select(
            func.count().filter(~voided),
            func.coalesce(func.sum(sub.c.total).filter(~voided), 0),
            func.coalesce(func.sum(sub.c.tax_total).filter(~voided), 0),
            func.count().filter(voided),
            func.coalesce(func.sum(sub.c.total).filter(voided), 0),
        )).one()
        return SaleTotals(int(row[0]), Decimal(row[1]), Decimal(row[2]), int(row[3]), Decimal(row[4]))

    def day_by_method(self, day: date) -> List[Tuple[PaymentMethod, int, Decimal, Decimal]]:
        rows = self._db.execute(
            select(Sale.method, func.count(), func.coalesce(func.sum(Sale.total), 0), func.coalesce(func.sum(Sale.tax_total), 0))
            .where(Sale.gym_id == self._gym_id, Sale.sale_date == day, Sale.voided_at.is_(None))
            .group_by(Sale.method)
        ).all()
        return [(m, int(c), Decimal(t), Decimal(x)) for m, c, t, x in rows]

    def voided_on(self, day: date) -> Tuple[int, Decimal]:
        row = self._db.execute(
            select(func.count(), func.coalesce(func.sum(Sale.total), 0)).where(
                Sale.gym_id == self._gym_id, Sale.sale_date == day, Sale.voided_at.is_not(None)
            )
        ).one()
        return int(row[0]), Decimal(row[1])
