"""Schemas de sesiones de caja (apertura, cierre con arqueo y resumen del turno)."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.cash_session import CashSessionStatus
from app.models.payment import PaymentMethod

CashAmount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


def _blank_to_none(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v or None


class CashSessionOpen(BaseModel):
    opening_float: CashAmount            # fondo inicial (caja chica)
    notes: Optional[str] = Field(None, max_length=1000)

    _notes = field_validator("notes")(_blank_to_none)


class CashSessionClose(BaseModel):
    counted_cash: CashAmount             # efectivo contado físicamente en la gaveta
    notes: Optional[str] = Field(None, max_length=1000)

    _notes = field_validator("notes")(_blank_to_none)


class CashierOut(BaseModel):
    id: uuid.UUID
    full_name: str


class SessionMethodTotalOut(BaseModel):
    method: PaymentMethod
    payments_count: int
    payments_total: Decimal
    sales_count: int
    sales_total: Decimal
    total: Decimal


class CashSessionSummaryOut(BaseModel):
    """Movimientos del turno, calculados en vivo (excluye lo anulado)."""
    payments_count: int
    payments_total: Decimal
    sales_count: int
    sales_total: Decimal
    sales_tax_total: Decimal
    total: Decimal
    by_method: List[SessionMethodTotalOut]
    cash_payments_total: Decimal
    cash_sales_total: Decimal
    expected_cash: Decimal               # fondo inicial + efectivo cobrado
    voided_count: int
    voided_total: Decimal


class CashSessionOut(BaseModel):
    id: uuid.UUID
    cashier: CashierOut
    status: CashSessionStatus
    business_date: date
    opened_at: datetime
    opening_float: Decimal
    opening_notes: Optional[str]
    closed_at: Optional[datetime]
    closed_by_name: Optional[str]
    # Instantánea del cierre (auditoría): no cambia aunque luego se anule algo.
    cash_payments_total: Optional[Decimal]
    cash_sales_total: Optional[Decimal]
    expected_cash: Optional[Decimal]
    counted_cash: Optional[Decimal]
    difference: Optional[Decimal]        # contado − esperado: + sobrante, − faltante
    closing_notes: Optional[str]
    currency: str
    summary: CashSessionSummaryOut


class CurrentCashSessionOut(BaseModel):
    """GET /cash-sessions/current: la caja abierta del usuario, o null si no tiene."""
    session: Optional[CashSessionOut]


class CashSessionListItemOut(BaseModel):
    id: uuid.UUID
    cashier: CashierOut
    status: CashSessionStatus
    business_date: date
    opened_at: datetime
    closed_at: Optional[datetime]
    opening_float: Decimal
    expected_cash: Optional[Decimal]
    counted_cash: Optional[Decimal]
    difference: Optional[Decimal]


class CashSessionListOut(BaseModel):
    items: List[CashSessionListItemOut]
    total: int
    page: int
    size: int
    pages: int
