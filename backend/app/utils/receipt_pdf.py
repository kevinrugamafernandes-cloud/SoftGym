"""Comprobante de pago en PDF (ReportLab). Solo usa fuentes base: sin archivos externos."""
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

GOLD = HexColor("#A39165")
INK = HexColor("#111111")
MUTED = HexColor("#666666")
RED = HexColor("#B42318")


def format_money(amount: Decimal, currency: str) -> str:
    """"CRC 25 000,00" (coma decimal, espacio de miles). Se usa el código de moneda: las fuentes base
    del PDF no incluyen el signo ₡."""
    whole, _, frac = f"{Decimal(amount):.2f}".partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return f"{currency} {' '.join(groups)},{frac}"


def format_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


@dataclass
class ReceiptData:
    gym_name: str
    currency: str
    receipt_code: str
    payment_date: date
    member_name: str
    member_identification: str
    plan_name: str
    period_start: date
    period_end: date
    amount: Decimal
    list_price: Optional[Decimal]
    method_label: str
    reference: Optional[str]
    registered_by: Optional[str]
    voided_on: Optional[date] = None
    void_reason: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    business: Optional[str] = None          # razón social · cédula · teléfono · dirección
    footer: Optional[str] = None            # mensaje personalizado del gimnasio


def business_line(legal_name: Optional[str], tax_id: Optional[str], phone: Optional[str], address: Optional[str]) -> Optional[str]:
    parts = [legal_name, f"Céd. {tax_id}" if tax_id else None, f"Tel. {phone}" if phone else None, address]
    text = " · ".join(p for p in parts if p)
    return text or None


def build_receipt_pdf(r: ReceiptData) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A5)
    c.setTitle(f"Comprobante {r.receipt_code}")
    width, height = A5
    left, right = 15 * mm, width - 15 * mm

    # Encabezado
    c.setFillColor(GOLD)
    c.rect(0, height - 28 * mm, width, 28 * mm, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(left, height - 14 * mm, r.gym_name)
    c.setFont("Helvetica", 9)
    c.drawString(left, height - 21 * mm, "Comprobante de pago")
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(right, height - 14 * mm, r.receipt_code)
    c.setFont("Helvetica", 9)
    c.drawRightString(right, height - 21 * mm, f"Fecha: {format_date(r.payment_date)}")

    y = height - 42 * mm

    def row(label: str, value: str, bold: bool = False) -> None:
        nonlocal y
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(left, y, label)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 11 if bold else 10)
        c.drawString(left + 38 * mm, y, value)
        y -= 8 * mm

    row("Socio", r.member_name)
    row("Cédula", r.member_identification)
    row("Plan", r.plan_name)
    row("Periodo cubierto", f"{format_date(r.period_start)} al {format_date(r.period_end)}")
    row("Método de pago", r.method_label)
    if r.reference:
        row("Referencia", r.reference)
    if r.list_price is not None and r.list_price > r.amount:
        row("Precio del plan", format_money(r.list_price, r.currency))
        row("Descuento", format_money(r.list_price - r.amount, r.currency))

    if r.tax_rate is not None and r.subtotal is not None and r.tax_amount is not None:
        if r.tax_rate > 0:
            row("Subtotal sin IVA", format_money(r.subtotal, r.currency))
            row(f"IVA {r.tax_rate.normalize():f} %", format_money(r.tax_amount, r.currency))
        else:
            row("IVA", "Exento")

    y -= 2 * mm
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(left, y + 4 * mm, right, y + 4 * mm)
    row("TOTAL PAGADO", format_money(r.amount, r.currency), bold=True)

    if r.registered_by:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(left, 22 * mm, f"Atendido por: {r.registered_by}")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 14 * mm, (r.footer or "Gracias por entrenar con nosotros.")[:95])
    if r.business:
        c.setFont("Helvetica", 7)
        c.drawCentredString(width / 2, 9 * mm, r.business[:110])

    # Marca de agua si el pago fue anulado
    if r.voided_on:
        c.saveState()
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 44)
        c.translate(width / 2, height / 2)
        c.rotate(30)
        c.drawCentredString(0, 0, "ANULADO")
        c.restoreState()
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left, 32 * mm, f"Anulado el {format_date(r.voided_on)}")
        if r.void_reason:
            c.setFont("Helvetica", 8)
            c.drawString(left, 27 * mm, f"Motivo: {r.void_reason[:80]}")

    c.showPage()
    c.save()
    return buf.getvalue()
