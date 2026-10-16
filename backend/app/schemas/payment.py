"""Schemas del módulo de pagos y caja."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.payment import Payment, PaymentMethod
from app.utils.money import split_tax_included

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


def receipt_code(number: int) -> str:
    return f"R-{number:06d}"


class PaymentCreate(BaseModel):
    member_id: uuid.UUID
    plan_id: uuid.UUID
    # Si se omite se cobra el precio del plan; un monto distinto se registra como descuento.
    amount: Optional[Money] = None
    method: PaymentMethod
    payment_date: Optional[date] = None   # por defecto: hoy en la zona horaria del gimnasio
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)
    # Confirma un cobro que parece duplicado (mismo socio, plan y monto hace instantes).
    confirm_duplicate: bool = False

    @field_validator("reference", "notes")
    @classmethod
    def blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class VoidRequest(BaseModel):
    reason: str = Field(..., max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Indique el motivo de la anulación (mínimo 5 caracteres)")
        return v


class PaymentMemberOut(BaseModel):
    id: uuid.UUID
    full_name: str
    identification: str


class PaymentPlanOut(BaseModel):
    id: uuid.UUID
    name: str
    duration_days: int


class PaymentPeriodOut(BaseModel):
    start_date: date
    end_date: date


class PaymentOut(BaseModel):
    id: uuid.UUID
    receipt_number: int
    receipt_code: str
    member: PaymentMemberOut
    plan: PaymentPlanOut
    period: PaymentPeriodOut
    amount: Decimal
    list_price: Optional[Decimal]
    discount: Decimal                      # list_price - amount si fue menor; si no, 0
    tax_rate: Decimal                      # IVA incluido en `amount`
    subtotal: Decimal                      # base sin IVA
    tax_amount: Decimal
    method: PaymentMethod
    payment_date: date
    reference: Optional[str]
    notes: Optional[str]
    registered_by_name: Optional[str]
    cash_session_id: Optional[uuid.UUID]
    is_voided: bool
    voided_at: Optional[datetime]
    voided_by_name: Optional[str]
    void_reason: Optional[str]
    created_at: datetime

    @classmethod
    def from_payment(cls, p: Payment) -> "PaymentOut":
        ms = p.membership
        discount = max(Decimal("0"), (p.list_price - p.amount)) if p.list_price is not None else Decimal("0")
        base, tax = split_tax_included(p.amount, p.tax_rate)
        return cls(
            id=p.id,
            receipt_number=p.receipt_number,
            receipt_code=receipt_code(p.receipt_number),
            member=PaymentMemberOut(id=ms.member.id, full_name=ms.member.full_name, identification=ms.member.identification),
            plan=PaymentPlanOut(id=ms.plan.id, name=ms.plan.name, duration_days=ms.plan.duration_days),
            period=PaymentPeriodOut(start_date=ms.start_date, end_date=ms.end_date),
            amount=p.amount,
            list_price=p.list_price,
            discount=discount,
            tax_rate=p.tax_rate,
            subtotal=base,
            tax_amount=tax,
            method=p.method,
            payment_date=p.payment_date,
            reference=p.reference,
            notes=p.notes,
            registered_by_name=p.registered_by.full_name if p.registered_by else None,
            cash_session_id=p.cash_session_id,
            is_voided=p.voided_at is not None,
            voided_at=p.voided_at,
            voided_by_name=p.voided_by.full_name if p.voided_by else None,
            void_reason=p.void_reason,
            created_at=p.created_at,
        )


class PaymentTotalsOut(BaseModel):
    active_count: int
    active_total: Decimal
    voided_count: int
    voided_total: Decimal


class PaymentListOut(BaseModel):
    items: List[PaymentOut]
    total: int
    page: int
    size: int
    pages: int
    totals: PaymentTotalsOut      # de TODO el filtro (no solo de la página)


class MethodTotalOut(BaseModel):
    method: PaymentMethod
    count: int
    total: Decimal


class CashSummaryOut(BaseModel):
    """Cierre del día (todas las cajas): cobros de membresía + ventas de la tienda, NO anulados."""
    date: date
    currency: str
    count: int
    total: Decimal
    by_method: List[MethodTotalOut]
    voided_count: int
    voided_total: Decimal
    payments_count: int = 0
    payments_total: Decimal = Decimal(0)
    sales_count: int = 0
    sales_total: Decimal = Decimal(0)
    sales_tax_total: Decimal = Decimal(0)


class ReceiptGymOut(BaseModel):
    name: str
    currency: str
    timezone: str
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    address: Optional[str] = None
    receipt_message: Optional[str] = None


class ReceiptOut(BaseModel):
    gym: ReceiptGymOut
    payment: PaymentOut
