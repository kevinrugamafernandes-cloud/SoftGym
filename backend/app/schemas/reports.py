"""Reportes contables: libro de ventas con IVA por tarifa y cierre mensual."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.payment import PaymentMethod

DocType = Literal["membresia", "venta"]


class TaxLineOut(BaseModel):
    rate: Decimal
    base: Decimal
    tax: Decimal


class SalesBookRowOut(BaseModel):
    date: date
    doc_type: DocType
    document: str                  # R-000123 (membresía) · V-000045 (tienda)
    customer: Optional[str]
    identification: Optional[str]
    detail: str                    # plan o productos
    method: PaymentMethod
    reference: Optional[str]
    cashier: Optional[str]
    taxes: List[TaxLineOut]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    voided: bool
    void_reason: Optional[str]


class RateTotalOut(BaseModel):
    rate: Decimal
    base: Decimal
    tax: Decimal
    total: Decimal


class TypeTotalOut(BaseModel):
    doc_type: DocType
    count: int
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal


class MethodTotalOut(BaseModel):
    method: PaymentMethod
    count: int
    total: Decimal


class DayTotalOut(BaseModel):
    date: date
    memberships: Decimal
    store: Decimal
    tax_total: Decimal
    total: Decimal


class CashSessionsTotalsOut(BaseModel):
    count: int
    open_count: int
    expected_total: Decimal
    counted_total: Decimal
    difference_total: Decimal       # neto: + sobrante, − faltante
    shortages_total: Decimal        # suma de faltantes (positivo)
    overages_total: Decimal         # suma de sobrantes


class ReportSummaryOut(BaseModel):
    """Totales de un periodo. NO incluyen documentos anulados (van aparte)."""
    currency: str
    date_from: date
    date_to: date
    count: int
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    by_rate: List[RateTotalOut]
    by_type: List[TypeTotalOut]
    by_method: List[MethodTotalOut]
    by_day: List[DayTotalOut]
    voided_count: int
    voided_total: Decimal
    cash_sessions: CashSessionsTotalsOut


class SalesBookOut(BaseModel):
    summary: ReportSummaryOut
    rows: List[SalesBookRowOut]


class MonthlyReportOut(BaseModel):
    year: int
    month: int
    label: str                      # "octubre 2026"
    date_from: date
    date_to: date
    status: Literal["en_curso", "abierto", "cerrado"]
    can_close: bool
    close_blockers: List[str]       # por qué todavía no se puede cerrar
    closed_at: Optional[datetime]
    closed_by_name: Optional[str]
    notes: Optional[str]
    summary: ReportSummaryOut       # si está cerrado: la instantánea entregada al contador


class MonthlyCloseCreate(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    notes: Optional[str] = Field(None, max_length=1000)


class MonthlyCloseItemOut(BaseModel):
    id: uuid.UUID
    year: int
    month: int
    label: str
    closed_at: datetime
    closed_by_name: Optional[str]
    total: Decimal
    tax_total: Decimal
