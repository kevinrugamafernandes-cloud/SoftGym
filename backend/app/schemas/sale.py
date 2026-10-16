"""Schemas de ventas del punto de venta."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.payment import PaymentMethod

MAX_LINES = 50


def sale_code(number: int) -> str:
    return f"V-{number:06d}"


class SaleLineIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=999)


class SaleCreate(BaseModel):
    """Los precios NO vienen del cliente: se toman del producto en el servidor."""
    items: List[SaleLineIn] = Field(..., min_length=1, max_length=MAX_LINES)
    method: PaymentMethod
    reference: Optional[str] = Field(None, max_length=100)
    member_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = Field(None, max_length=160)
    customer_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("reference", "customer_name", "customer_phone", "notes")
    @classmethod
    def blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = " ".join(v.split()) if v else v
        return v or None


class SaleVoid(BaseModel):
    reason: str = Field(..., max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Indique el motivo de la anulación (mínimo 5 caracteres)")
        return v


class SaleItemOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    cabys_code: Optional[str]
    quantity: int
    unit_price: Decimal
    tax_rate: Decimal
    line_subtotal: Decimal
    line_tax: Decimal
    line_total: Decimal


class TaxBreakdownOut(BaseModel):
    rate: Decimal
    base: Decimal
    tax: Decimal


class SaleCustomerOut(BaseModel):
    member_id: Optional[uuid.UUID]
    name: Optional[str]
    phone: Optional[str]


class SaleOut(BaseModel):
    id: uuid.UUID
    sale_number: int
    sale_code: str
    sale_date: date
    created_at: datetime
    cash_session_id: uuid.UUID
    cashier_name: Optional[str]
    customer: SaleCustomerOut
    method: PaymentMethod
    reference: Optional[str]
    items: List[SaleItemOut]
    taxes: List[TaxBreakdownOut]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    notes: Optional[str]
    is_voided: bool
    voided_at: Optional[datetime]
    voided_by_name: Optional[str]
    void_reason: Optional[str]


class SaleTotalsOut(BaseModel):
    active_count: int
    active_total: Decimal
    active_tax: Decimal
    voided_count: int
    voided_total: Decimal


class SaleListOut(BaseModel):
    items: List[SaleOut]
    total: int
    page: int
    size: int
    pages: int
    totals: SaleTotalsOut


class WhatsAppLinkOut(BaseModel):
    phone: str
    url: str
    message: str
