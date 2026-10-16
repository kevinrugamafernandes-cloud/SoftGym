import math
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import settings
from app.core.exceptions import BusinessRuleException, ConflictException, NotFoundException
from app.models.membership import Membership, MembershipStatus
from app.models.payment import Payment, PaymentMethod
from app.models.user import User
from app.repositories.member_repository import MemberRepository
from app.repositories.membership_repository import MembershipRepository
from app.repositories.payment_repository import PaymentFilters, PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.payment import (
    CashSummaryOut, MethodTotalOut, PaymentCreate, PaymentListOut, PaymentOut, PaymentTotalsOut,
    ReceiptGymOut, ReceiptOut,
)
from app.schemas.sale import WhatsAppLinkOut
from app.services.cash_session_service import CashSessionService, cash_session_required
from app.services.membership_service import MembershipService
from app.services.membership_status import sync_member_status
from app.services.period_lock import ensure_period_open
from app.utils.receipt_pdf import ReceiptData, build_receipt_pdf, business_line
from app.utils.whatsapp import normalize_phone, payment_message, wa_link

METHOD_LABELS = {
    PaymentMethod.CASH: "Efectivo", PaymentMethod.CARD: "Tarjeta", PaymentMethod.TRANSFER: "Transferencia",
    PaymentMethod.SINPE: "SINPE Móvil", PaymentMethod.OTHER: "Otro",
}
# Estos métodos se concilian contra el estado bancario: el número de referencia es obligatorio.
_REFERENCE_REQUIRED = {PaymentMethod.SINPE, PaymentMethod.TRANSFER}


class PaymentService:
    def __init__(self, db: Session, gym_id: uuid.UUID, clock: Clock) -> None:
        self._db = db
        self._gym_id = gym_id
        self._clock = clock
        self._members = MemberRepository(db, gym_id)
        self._plans = PlanRepository(db, gym_id)
        self._memberships = MembershipRepository(db, gym_id)
        self._payments = PaymentRepository(db, gym_id)
        self._info = MembershipService(db, gym_id, clock)
        self._sales = SaleRepository(db, gym_id)

    # ── Cobrar ────────────────────────────────────────────────────────────────
    def register(self, data: PaymentCreate, user: User) -> PaymentOut:
        try:
            payment = self.register_in_transaction(data, user)
            self._db.commit()
        except Exception:
            self._db.rollback()  # todo o nada: ni membresía, ni comprobante, ni cambio de estado
            raise
        return PaymentOut.from_payment(self._load(payment.id))

    def register_in_transaction(self, data: PaymentCreate, user: User) -> Payment:
        """Igual que register() pero SIN commit: lo usa la inscripción (socio + cobro en una transacción)."""
        return self._register(data, user)

    def _register(self, data: PaymentCreate, user: User) -> Payment:
        """
        Registra un cobro y, en la MISMA transacción: crea el periodo de membresía, asigna el
        número de comprobante y actualiza el estado del socio. Todo o nada.

        Regla de vigencia: si el socio aún tiene membresía vigente, el nuevo periodo empieza el día
        siguiente a su vencimiento (renovar antes NO hace perder días); si ya venció o nunca tuvo,
        empieza en la fecha del pago.
        """
        member = self._members.get_for_update(data.member_id)  # bloquea: dos cobros simultáneos no se solapan
        if member is None:
            raise NotFoundException("Socio", code="member_not_found")
        plan = self._plans.get(data.plan_id)
        if plan is None:
            raise NotFoundException("Plan", code="plan_not_found")
        if not plan.is_active:
            raise BusinessRuleException(
                f"El plan '{plan.name}' está inactivo y no se puede vender", code="plan_inactive"
            )

        # Turno de caja: el cobro entra en el arqueo de quien lo registra.
        session = CashSessionService(self._db, self._gym_id, self._clock).lock_open_for(user)
        if session is None and settings.CASH_SESSION_REQUIRED:
            raise cash_session_required()

        today = self._info.today
        paid_on = data.payment_date or today
        if paid_on > today:
            raise BusinessRuleException("La fecha del pago no puede ser futura", code="payment_in_future")
        ensure_period_open(self._db, self._gym_id, paid_on, "registrar cobros con fecha de ese mes")

        amount = data.amount if data.amount is not None else plan.price
        if data.method in _REFERENCE_REQUIRED and not data.reference:
            raise BusinessRuleException(
                f"Para pagos por {METHOD_LABELS[data.method]} indique el número de referencia o comprobante",
                code="reference_required",
            )
        if not data.confirm_duplicate and self._payments.find_recent_duplicate(member.id, plan.id, amount):
            raise ConflictException(
                "Se acaba de registrar un pago idéntico para este socio. Si es un cobro distinto, "
                "confírmelo para continuar",
                code="possible_duplicate",
            )

        latest = self._memberships.latest_for_member(member.id)
        start = latest.end_date + timedelta(days=1) if latest and latest.end_date >= paid_on else paid_on
        end = start + timedelta(days=plan.duration_days - 1)

        membership = self._memberships.add(Membership(
            gym_id=self._gym_id, member_id=member.id, plan_id=plan.id, start_date=start, end_date=end,
            status=MembershipStatus.ACTIVE if end >= today else MembershipStatus.EXPIRED,
        ))
        payment = self._payments.add(Payment(
            gym_id=self._gym_id, membership_id=membership.id, registered_by_id=user.id,
            cash_session_id=session.id if session else None,
            receipt_number=self._payments.next_receipt_number(),
            amount=amount, list_price=plan.price, tax_rate=plan.tax_rate, payment_date=paid_on, method=data.method,
            reference=data.reference, notes=data.notes,
        ))

        sync_member_status(
            member, self._memberships.latest_for_member(member.id), today,
            warn_days=settings.MEMBERSHIP_EXPIRING_DAYS, grace_days=settings.MEMBERSHIP_GRACE_DAYS,
            reactivate=True,  # pagar reactiva a un socio inactivo
        )
        self._db.flush()
        return payment

    # ── Anular ────────────────────────────────────────────────────────────────
    def void(self, payment_id: uuid.UUID, reason: str, user: User) -> PaymentOut:
        try:
            return self._void(payment_id, reason, user)
        except Exception:
            self._db.rollback()
            raise

    def _void(self, payment_id: uuid.UUID, reason: str, user: User) -> PaymentOut:
        """
        Los pagos no se borran: se ANULAN conservando quién, cuándo y por qué. Solo se puede anular el
        ÚLTIMO pago del socio (si no, los periodos posteriores quedarían con huecos).
        """
        payment = self._payments.get(payment_id)
        if payment is None:
            raise NotFoundException("Pago", code="payment_not_found")
        if payment.voided_at is not None:
            raise ConflictException("El pago ya está anulado", code="already_voided")
        ensure_period_open(self._db, self._gym_id, payment.payment_date, "anular cobros de ese mes")

        member = self._members.get_for_update(payment.membership.member_id, include_deleted=True)
        latest_payment = self._payments.latest_active_for_member(member.id) if member else None
        if latest_payment is None or latest_payment.id != payment.id:
            raise ConflictException(
                "Solo se puede anular el último pago del socio. Anule primero el pago más reciente",
                code="void_latest_first",
            )

        payment.voided_at = self._clock.now()
        payment.voided_by_id = user.id
        payment.void_reason = reason
        payment.membership.status = MembershipStatus.CANCELLED
        self._db.flush()

        sync_member_status(
            member, self._memberships.latest_for_member(member.id), self._info.today,
            warn_days=settings.MEMBERSHIP_EXPIRING_DAYS, grace_days=settings.MEMBERSHIP_GRACE_DAYS,
            reactivate=False,
        )
        self._db.commit()
        return PaymentOut.from_payment(self._load(payment.id))

    # ── Consultas ─────────────────────────────────────────────────────────────
    def _load(self, payment_id: uuid.UUID) -> Payment:
        payment = self._payments.get(payment_id)
        if payment is None:
            raise NotFoundException("Pago", code="payment_not_found")
        self._db.refresh(payment)
        return payment

    def get(self, payment_id: uuid.UUID) -> PaymentOut:
        payment = self._payments.get(payment_id)
        if payment is None:
            raise NotFoundException("Pago", code="payment_not_found")
        return PaymentOut.from_payment(payment)

    def list(self, filters: PaymentFilters, *, page: int, size: int) -> PaymentListOut:
        items, total = self._payments.search(filters, page=page, size=size)
        t = self._payments.totals(filters)
        return PaymentListOut(
            items=[PaymentOut.from_payment(p) for p in items], total=total, page=page, size=size,
            pages=math.ceil(total / size) if total else 0,
            totals=PaymentTotalsOut(active_count=t.active_count, active_total=t.active_total,
                                    voided_count=t.voided_count, voided_total=t.voided_total),
        )

    def cash_summary(self, day: Optional[date]) -> CashSummaryOut:
        """
        Cierre del DÍA (todas las cajas): cobros de membresía + ventas de la tienda, sin anulados.
        `total`/`count`/`by_method` suman ambos; los campos payments_* y sales_* los separan.
        """
        day = day or self._info.today
        merged: dict = {}
        for m, c, t in self._payments.cash_by_method(day):
            merged[m] = [c, t]
        sales_count, sales_total, sales_tax = 0, Decimal(0), Decimal(0)
        for m, c, t, x in self._sales.day_by_method(day):
            row = merged.setdefault(m, [0, Decimal(0)])
            row[0] += c
            row[1] += t
            sales_count, sales_total, sales_tax = sales_count + c, sales_total + t, sales_tax + x
        order = list(PaymentMethod)
        by_method = [MethodTotalOut(method=m, count=c, total=t) for m, (c, t) in sorted(merged.items(), key=lambda kv: order.index(kv[0]))]
        p_voided_count, p_voided_total = self._payments.voided_on(day)
        s_voided_count, s_voided_total = self._sales.voided_on(day)
        count = sum(r.count for r in by_method)
        total = sum((r.total for r in by_method), start=Decimal(0))
        return CashSummaryOut(
            date=day, currency=self._info.gym.currency, count=count, total=total, by_method=by_method,
            voided_count=p_voided_count + s_voided_count, voided_total=p_voided_total + s_voided_total,
            payments_count=count - sales_count, payments_total=total - sales_total,
            sales_count=sales_count, sales_total=sales_total, sales_tax_total=sales_tax,
        )

    # ── Comprobante ───────────────────────────────────────────────────────────
    def receipt(self, payment_id: uuid.UUID) -> ReceiptOut:
        out = self.get(payment_id)
        return ReceiptOut(
            gym=ReceiptGymOut(
                name=self._info.gym.name, currency=self._info.gym.currency, timezone=self._info.gym.timezone,
                legal_name=self._info.gym.legal_name, tax_id=self._info.gym.tax_id,
                whatsapp_phone=self._info.gym.whatsapp_phone, address=self._info.gym.address,
                receipt_message=self._info.gym.receipt_message,
            ),
            payment=out,
        )

    def receipt_pdf(self, payment_id: uuid.UUID) -> tuple[str, bytes]:
        r = self.receipt(payment_id)
        p = r.payment
        pdf = build_receipt_pdf(ReceiptData(
            gym_name=r.gym.name, currency=r.gym.currency, receipt_code=p.receipt_code,
            payment_date=p.payment_date, member_name=p.member.full_name, member_identification=p.member.identification,
            plan_name=p.plan.name, period_start=p.period.start_date, period_end=p.period.end_date,
            amount=p.amount, list_price=p.list_price, method_label=METHOD_LABELS[p.method],
            reference=p.reference, registered_by=p.registered_by_name,
            tax_rate=p.tax_rate, subtotal=p.subtotal, tax_amount=p.tax_amount,
            business=business_line(r.gym.legal_name, r.gym.tax_id, r.gym.whatsapp_phone, r.gym.address),
            footer=r.gym.receipt_message,
            # La fecha de anulación es la del GIMNASIO: el instante está en UTC y tras las 6 p. m. ya es "mañana" allá.
            voided_on=p.voided_at.astimezone(ZoneInfo(r.gym.timezone)).date() if p.voided_at else None,
            void_reason=p.void_reason,
        ))
        return p.receipt_code, pdf

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    def whatsapp(self, payment_id: uuid.UUID, phone: Optional[str]) -> WhatsAppLinkOut:
        payment = self._payments.get(payment_id)
        if payment is None:
            raise NotFoundException("Pago", code="payment_not_found")
        p = PaymentOut.from_payment(payment)
        raw = phone or payment.membership.member.phone
        number = normalize_phone(raw)
        if number is None:
            raise BusinessRuleException(
                "Indique un número de WhatsApp válido (8 dígitos en Costa Rica)" if raw
                else "El socio no tiene teléfono registrado: indique un número de WhatsApp",
                code="phone_required",
            )
        message = payment_message(
            gym_name=self._info.gym.name, currency=self._info.gym.currency, code=p.receipt_code,
            payment_date=p.payment_date, member_name=p.member.full_name, plan_name=p.plan.name,
            period_start=p.period.start_date, period_end=p.period.end_date, amount=p.amount,
            method_label=METHOD_LABELS[p.method], reference=p.reference, voided=p.is_voided,
            footer=self._info.gym.receipt_message,
        )
        return WhatsAppLinkOut(phone=number, url=wa_link(number, message), message=message)
