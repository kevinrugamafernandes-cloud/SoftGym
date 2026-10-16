"""
Libro de ventas y cierre mensual (Costa Rica).

Unifica en un solo libro los cobros de MEMBRESÍAS (servicio gravado, IVA incluido en el precio)
y las ventas de la TIENDA (IVA por línea según la tarifa del producto). Todo se calcula con
Decimal y redondeo comercial; los anulados se listan pero no suman.

El cierre mensual guarda una instantánea de los totales y bloquea el periodo (ver period_lock).
"""
import calendar
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.clock import Clock
from app.core.exceptions import BusinessRuleException, ConflictException
from app.models.cash_session import CashSession, CashSessionStatus
from app.models.membership import Membership
from app.models.monthly_close import MonthlyClose
from app.models.payment import Payment, PaymentMethod
from app.models.sale import Sale
from app.models.user import User
from app.schemas.payment import receipt_code
from app.schemas.reports import (
    CashSessionsTotalsOut, DayTotalOut, MethodTotalOut, MonthlyCloseItemOut, MonthlyReportOut, RateTotalOut,
    ReportSummaryOut, SalesBookOut, SalesBookRowOut, TaxLineOut, TypeTotalOut,
)
from app.schemas.sale import sale_code
from app.services.gym_context import GymContext
from app.services.period_lock import month_label
from app.utils.money import q2, split_tax_included

ZERO = Decimal("0.00")
MAX_RANGE_DAYS = 366


def month_range(year: int, month: int) -> Tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


class ReportService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._ctx = GymContext(db, gym_id, clock)

    # ── Libro de ventas ───────────────────────────────────────────────────────
    def sales_book(self, date_from: date, date_to: date) -> SalesBookOut:
        if date_from > date_to:
            raise BusinessRuleException("La fecha inicial es posterior a la final", code="invalid_range")
        if (date_to - date_from).days >= MAX_RANGE_DAYS:
            raise BusinessRuleException("El rango máximo es de un año", code="range_too_long")
        rows = self._rows(date_from, date_to)
        return SalesBookOut(summary=self._summary(rows, date_from, date_to), rows=rows)

    def _rows(self, date_from: date, date_to: date) -> List[SalesBookRowOut]:
        rows: List[SalesBookRowOut] = []
        payments = self._db.scalars(
            select(Payment)
            .where(Payment.gym_id == self._gym_id, Payment.payment_date >= date_from, Payment.payment_date <= date_to)
            .options(
                selectinload(Payment.membership).selectinload(Membership.member),
                selectinload(Payment.membership).selectinload(Membership.plan),
                selectinload(Payment.registered_by),
            )
        ).all()
        for p in payments:
            base, tax = split_tax_included(p.amount, p.tax_rate)
            ms = p.membership
            rows.append(SalesBookRowOut(
                date=p.payment_date, doc_type="membresia", document=receipt_code(p.receipt_number),
                customer=ms.member.full_name, identification=ms.member.identification,
                detail=f"Membresía {ms.plan.name} ({ms.start_date:%d/%m/%Y} al {ms.end_date:%d/%m/%Y})",
                method=p.method, reference=p.reference,
                cashier=p.registered_by.full_name if p.registered_by else None,
                taxes=[TaxLineOut(rate=p.tax_rate, base=base, tax=tax)],
                subtotal=base, tax_total=tax, total=q2(p.amount),
                voided=p.voided_at is not None, void_reason=p.void_reason,
            ))

        sales = self._db.scalars(
            select(Sale)
            .where(Sale.gym_id == self._gym_id, Sale.sale_date >= date_from, Sale.sale_date <= date_to)
            .options(selectinload(Sale.items), selectinload(Sale.member), selectinload(Sale.cashier))
        ).all()
        for s in sales:
            acc: Dict[Decimal, List[Decimal]] = {}
            for it in s.items:
                b, t = acc.get(it.tax_rate, [ZERO, ZERO])
                acc[it.tax_rate] = [b + it.line_subtotal, t + it.line_tax]
            rows.append(SalesBookRowOut(
                date=s.sale_date, doc_type="venta", document=sale_code(s.sale_number),
                customer=s.customer_name or (s.member.full_name if s.member else None),
                identification=s.member.identification if s.member else None,
                detail=", ".join(f"{i.quantity}× {i.product_name}" for i in s.items),
                method=s.method, reference=s.reference, cashier=s.cashier.full_name if s.cashier else None,
                taxes=[TaxLineOut(rate=r, base=q2(b), tax=q2(t)) for r, (b, t) in sorted(acc.items(), reverse=True)],
                subtotal=s.subtotal, tax_total=s.tax_total, total=s.total,
                voided=s.voided_at is not None, void_reason=s.void_reason,
            ))
        rows.sort(key=lambda r: (r.date, r.doc_type, r.document))
        return rows

    def _summary(self, rows: List[SalesBookRowOut], date_from: date, date_to: date) -> ReportSummaryOut:
        active = [r for r in rows if not r.voided]
        voided = [r for r in rows if r.voided]

        by_rate: Dict[Decimal, List[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
        by_type: Dict[str, List] = {"membresia": [0, ZERO, ZERO, ZERO], "venta": [0, ZERO, ZERO, ZERO]}
        by_method: Dict[PaymentMethod, List] = defaultdict(lambda: [0, ZERO])
        by_day: Dict[date, List[Decimal]] = defaultdict(lambda: [ZERO, ZERO, ZERO])
        for r in active:
            for t in r.taxes:
                by_rate[t.rate][0] += t.base
                by_rate[t.rate][1] += t.tax
            bt = by_type[r.doc_type]
            bt[0] += 1
            bt[1] += r.subtotal
            bt[2] += r.tax_total
            bt[3] += r.total
            by_method[r.method][0] += 1
            by_method[r.method][1] += r.total
            day = by_day[r.date]
            day[0 if r.doc_type == "membresia" else 1] += r.total
            day[2] += r.tax_total
        # La tarifa general siempre aparece (aunque sea en cero): es la que revisa el contador.
        by_rate.setdefault(Decimal("13.00"), [ZERO, ZERO])
        methods = list(PaymentMethod)

        return ReportSummaryOut(
            currency=self._ctx.gym.currency, date_from=date_from, date_to=date_to, count=len(active),
            subtotal=q2(sum((r.subtotal for r in active), ZERO)),
            tax_total=q2(sum((r.tax_total for r in active), ZERO)),
            total=q2(sum((r.total for r in active), ZERO)),
            by_rate=[RateTotalOut(rate=q2(rate), base=q2(b), tax=q2(t), total=q2(b + t))
                     for rate, (b, t) in sorted(by_rate.items(), key=lambda kv: -kv[0])],
            by_type=[TypeTotalOut(doc_type=k, count=v[0], subtotal=q2(v[1]), tax_total=q2(v[2]), total=q2(v[3]))  # type: ignore[arg-type]
                     for k, v in by_type.items()],
            by_method=[MethodTotalOut(method=m, count=v[0], total=q2(v[1]))
                       for m, v in sorted(by_method.items(), key=lambda kv: methods.index(kv[0]))],
            by_day=[DayTotalOut(date=d, memberships=q2(v[0]), store=q2(v[1]), tax_total=q2(v[2]), total=q2(v[0] + v[1]))
                    for d, v in sorted(by_day.items())],
            voided_count=len(voided), voided_total=q2(sum((r.total for r in voided), ZERO)),
            cash_sessions=self._sessions(date_from, date_to),
        )

    def _sessions(self, date_from: date, date_to: date) -> CashSessionsTotalsOut:
        sessions = self._db.scalars(
            select(CashSession).where(
                CashSession.gym_id == self._gym_id,
                CashSession.business_date >= date_from, CashSession.business_date <= date_to,
            )
        ).all()
        closed = [s for s in sessions if s.status == CashSessionStatus.CLOSED]
        diffs = [s.difference or ZERO for s in closed]
        return CashSessionsTotalsOut(
            count=len(sessions), open_count=len(sessions) - len(closed),
            expected_total=q2(sum((s.expected_cash or ZERO for s in closed), ZERO)),
            counted_total=q2(sum((s.counted_cash or ZERO for s in closed), ZERO)),
            difference_total=q2(sum(diffs, ZERO)),
            shortages_total=q2(-sum((d for d in diffs if d < 0), ZERO)),
            overages_total=q2(sum((d for d in diffs if d > 0), ZERO)),
        )

    # ── Cierre mensual ────────────────────────────────────────────────────────
    def _close_row(self, year: int, month: int) -> Optional[MonthlyClose]:
        return self._db.scalars(
            select(MonthlyClose).options(selectinload(MonthlyClose.closed_by)).where(
                MonthlyClose.gym_id == self._gym_id, MonthlyClose.year == year, MonthlyClose.month == month
            )
        ).first()

    def _blockers(self, year: int, month: int) -> List[str]:
        first, last = month_range(year, month)
        out: List[str] = []
        if self._ctx.today <= last:
            out.append("El mes todavía no ha terminado")
        open_sessions = self._db.scalars(
            select(CashSession).options(selectinload(CashSession.cashier)).where(
                CashSession.gym_id == self._gym_id, CashSession.status == CashSessionStatus.OPEN,
                CashSession.business_date <= last,
            )
        ).all()
        for s in open_sessions:
            out.append(f"La caja de {s.cashier.full_name} (abierta el {s.business_date:%d/%m/%Y}) sigue abierta")
        return out

    def monthly(self, year: int, month: int) -> MonthlyReportOut:
        if not (1 <= month <= 12 and 2000 <= year <= 2100):
            raise BusinessRuleException("Periodo inválido", code="invalid_period")
        first, last = month_range(year, month)
        row = self._close_row(year, month)
        if row is not None:
            return MonthlyReportOut(
                year=year, month=month, label=month_label(year, month), date_from=first, date_to=last,
                status="cerrado", can_close=False, close_blockers=[], closed_at=row.closed_at,
                closed_by_name=row.closed_by.full_name if row.closed_by else None, notes=row.notes,
                summary=ReportSummaryOut.model_validate(row.summary),
            )
        blockers = self._blockers(year, month)
        return MonthlyReportOut(
            year=year, month=month, label=month_label(year, month), date_from=first, date_to=last,
            status="en_curso" if self._ctx.today <= last else "abierto", can_close=not blockers,
            close_blockers=blockers, closed_at=None, closed_by_name=None, notes=None,
            summary=self._summary(self._rows(first, last), first, last),
        )

    def close_month(self, year: int, month: int, notes: Optional[str], user: User) -> MonthlyReportOut:
        if self._close_row(year, month) is not None:
            raise ConflictException(f"{month_label(year, month).capitalize()} ya está cerrado", code="period_already_closed")
        blockers = self._blockers(year, month)
        if blockers:
            raise BusinessRuleException("No se puede cerrar el mes: " + "; ".join(blockers), code="period_not_closable")
        first, last = month_range(year, month)
        summary = self._summary(self._rows(first, last), first, last)
        try:
            self._db.add(MonthlyClose(
                gym_id=self._gym_id, year=year, month=month, summary=summary.model_dump(mode="json"),
                notes=(notes or "").strip() or None, closed_by_id=user.id,
            ))
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ConflictException(f"{month_label(year, month).capitalize()} ya está cerrado", code="period_already_closed")
        return self.monthly(year, month)

    def closes(self) -> List[MonthlyCloseItemOut]:
        rows = self._db.scalars(
            select(MonthlyClose).options(selectinload(MonthlyClose.closed_by))
            .where(MonthlyClose.gym_id == self._gym_id)
            .order_by(MonthlyClose.year.desc(), MonthlyClose.month.desc())
        ).all()
        return [
            MonthlyCloseItemOut(
                id=r.id, year=r.year, month=r.month, label=month_label(r.year, r.month), closed_at=r.closed_at,
                closed_by_name=r.closed_by.full_name if r.closed_by else None,
                total=Decimal(str(r.summary.get("total", "0"))), tax_total=Decimal(str(r.summary.get("tax_total", "0"))),
            )
            for r in rows
        ]

    # ── Exportaciones ─────────────────────────────────────────────────────────
    def sales_book_csv(self, date_from: date, date_to: date) -> bytes:
        from app.utils.report_export import sales_book_csv
        book = self.sales_book(date_from, date_to)
        return sales_book_csv(book, self._ctx.gym)

    def monthly_pdf(self, year: int, month: int) -> bytes:
        from app.utils.report_export import monthly_pdf
        report = self.monthly(year, month)
        rows = self._rows(report.date_from, report.date_to)
        return monthly_pdf(report, rows, self._ctx.gym, generated_on=self._ctx.today)

    def today(self) -> date:
        return self._ctx.today

    def default_month(self) -> Tuple[int, int]:
        """El mes anterior: el que normalmente se cierra y se entrega al contador."""
        prev = self._ctx.today.replace(day=1) - timedelta(days=1)
        return prev.year, prev.month
