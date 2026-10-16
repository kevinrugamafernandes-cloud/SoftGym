"""Ticket de venta en PDF, 80 mm de ancho (impresoras térmicas de recepción). Solo fuentes base."""
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.utils.receipt_pdf import format_date, format_money

INK = HexColor("#111111")
MUTED = HexColor("#555555")
RED = HexColor("#B42318")
WIDTH = 80 * mm
MARGIN = 5 * mm


@dataclass
class SaleTicketLine:
    quantity: int
    name: str
    unit_price: Decimal
    line_total: Decimal
    tax_rate: Decimal


@dataclass
class SaleTicketData:
    gym_name: str
    currency: str
    code: str
    sale_date: date
    created_at: datetime
    cashier: Optional[str]
    customer: Optional[str]
    lines: List[SaleTicketLine]
    subtotal: Decimal
    taxes: List[Tuple[Decimal, Decimal, Decimal]] = field(default_factory=list)   # (tarifa, base, impuesto)
    total: Decimal = Decimal("0")
    method_label: str = ""
    reference: Optional[str] = None
    voided: bool = False
    void_reason: Optional[str] = None
    footer: Optional[str] = None
    business: Optional[str] = None


def _wrap(text: str, max_chars: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > max_chars:
            if cur:
                lines.append(cur)
            cur = w[:max_chars]
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines or [""]


def build_sale_pdf(t: SaleTicketData) -> bytes:
    # Alto exacto según el contenido (en mm), para que el ticket no desperdicie papel.
    name_lines = [_wrap(l.name, 30) for l in t.lines]
    body = sum(len(n) * 4.2 + 4.6 for n in name_lines)
    business_lines = _wrap(t.business, 48)[:3] if t.business else []
    header = 9 + 5 + 4.2 * len(business_lines) + 4.2 + 5 + 4.2 + (4.2 if t.customer else 0) + 1.5
    footer = 1.5 + 4.2 * (2 + len(t.taxes)) + 1 + 4.2 + (4.2 if t.cashier else 0) + 2 + 4.2 * 2 + 8
    voided = (2 + 4.6 + 4.2 * len(_wrap(f"Motivo: {t.void_reason}", 44)[:3]) if t.void_reason else 6.6) if t.voided else 0
    height = (header + body + footer + voided) * mm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(WIDTH, height))
    c.setTitle(f"Venta {t.code}")
    left, right = MARGIN, WIDTH - MARGIN
    y = height - 9 * mm

    def text(s: str, *, size: float = 8, bold: bool = False, align: str = "left", color=INK, dy: float = 4.2) -> None:
        nonlocal y
        c.setFillColor(color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if align == "center":
            c.drawCentredString(WIDTH / 2, y, s)
        elif align == "right":
            c.drawRightString(right, y, s)
        else:
            c.drawString(left, y, s)
        y -= dy * mm

    def pair(label: str, value: str, *, bold: bool = False, size: float = 8) -> None:
        nonlocal y
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(left, y, label)
        c.drawRightString(right, y, value)
        y -= 4.2 * mm

    def rule() -> None:
        nonlocal y
        c.setStrokeColor(MUTED)
        c.setDash(1, 1.5)
        c.line(left, y + 2 * mm, right, y + 2 * mm)
        c.setDash()
        y -= 1.5 * mm

    text(t.gym_name, size=11, bold=True, align="center", dy=5)
    for line in business_lines:
        text(line, size=6.5, align="center", color=MUTED)
    text("Comprobante de venta", align="center", color=MUTED)
    text(t.code, size=10, bold=True, align="center", dy=5)
    text(f"{format_date(t.sale_date)}  {t.created_at.strftime('%H:%M')}", align="center", color=MUTED)
    if t.customer:
        text(f"Cliente: {t.customer[:40]}", align="center")
    rule()

    for line, names in zip(t.lines, name_lines):
        for i, n in enumerate(names):
            if i == len(names) - 1:
                pair(n, format_money(line.line_total, t.currency))
            else:
                text(n)
        text(f"  {line.quantity} x {format_money(line.unit_price, t.currency)}", size=7, color=MUTED, dy=4.6)
    rule()

    pair("Subtotal (sin IVA)", format_money(t.subtotal, t.currency))
    for rate, base, tax in t.taxes:
        if rate > 0:
            pair(f"IVA {rate.normalize():f} %", format_money(tax, t.currency))
        else:
            pair("Exento de IVA", format_money(base, t.currency))
    pair("TOTAL", format_money(t.total, t.currency), bold=True, size=10)
    y -= 1 * mm
    text(f"Pago: {t.method_label}" + (f"  Ref. {t.reference}" if t.reference else ""), color=MUTED)
    if t.cashier:
        text(f"Atendido por: {t.cashier}", color=MUTED)

    if t.voided:
        y -= 2 * mm
        text("*** VENTA ANULADA ***", size=10, bold=True, align="center", color=RED, dy=4.6)
        if t.void_reason:
            for part in _wrap(f"Motivo: {t.void_reason}", 44)[:3]:
                text(part, size=7, align="center", color=RED)

    y -= 2 * mm
    text(f"Precios con IVA incluido. {(t.footer or '¡Gracias por su compra!')[:60]}", size=7, align="center", color=MUTED)
    text("Documento interno: no es factura electrónica.", size=6, align="center", color=MUTED)

    c.showPage()
    c.save()
    return buf.getvalue()
