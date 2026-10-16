"""
Exportaciones para el contador: libro de ventas en CSV y cierre mensual en PDF.

CSV pensado para Excel en español: separador ";", coma decimal y BOM UTF-8 (abre con tildes
y montos correctos con doble clic). Los documentos ANULADOS aparecen con montos en cero y su
monto original aparte, para que sumar las columnas dé el total real.
"""
import csv
import io
from datetime import date
from decimal import Decimal
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

from app.models.gym import Gym
from app.schemas.reports import MonthlyReportOut, SalesBookOut, SalesBookRowOut
from app.utils.receipt_pdf import business_line

STANDARD_RATES = [Decimal("13.00"), Decimal("4.00"), Decimal("2.00"), Decimal("1.00")]
METHOD_LABELS = {"efectivo": "Efectivo", "tarjeta": "Tarjeta", "transferencia": "Transferencia",
                 "sinpe": "SINPE Móvil", "otro": "Otro"}
TYPE_LABELS = {"membresia": "Membresía", "venta": "Tienda"}
GOLD = colors.HexColor("#A39165")
LIGHT = colors.HexColor("#F3EFE6")
GRID = colors.HexColor("#D9D4C7")


def num(v: Decimal) -> str:
    """Formato para CSV (Excel en español): 1234,50 — sin separador de miles."""
    return f"{Decimal(v):.2f}".replace(".", ",")


def money(v: Decimal, currency: str = "CRC") -> str:
    whole, _, frac = f"{Decimal(v):.2f}".partition(".")
    neg = whole.startswith("-")
    whole = whole.lstrip("-")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    sym = "CRC " if currency == "CRC" else f"{currency} "   # las fuentes base del PDF no traen ₡
    return f"{'-' if neg else ''}{sym}{' '.join(groups)},{frac}"


def _rates(rows: List[SalesBookRowOut]) -> List[Decimal]:
    extra = sorted({t.rate for r in rows for t in r.taxes if t.rate > 0 and t.rate not in STANDARD_RATES}, reverse=True)
    return STANDARD_RATES + extra


def sales_book_csv(book: SalesBookOut, gym: Gym) -> bytes:
    rates = _rates(book.rows)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    s = book.summary
    w.writerow([f"Libro de ventas — {gym.name}"])
    if gym.legal_name or gym.tax_id:
        w.writerow([" · ".join(x for x in [gym.legal_name, f"Cédula {gym.tax_id}" if gym.tax_id else None] if x)])
    w.writerow([f"Periodo: {s.date_from:%d/%m/%Y} al {s.date_to:%d/%m/%Y}", f"Moneda: {s.currency}", "Precios con IVA incluido"])
    w.writerow([])
    header = ["Fecha", "Tipo", "Documento", "Cliente", "Identificación", "Detalle", "Método", "Referencia", "Estado"]
    for r in rates:
        header += [f"Gravado {r.normalize():f}%", f"IVA {r.normalize():f}%"]
    header += ["Exento", "Subtotal", "IVA total", "Total", "Monto anulado", "Motivo anulación", "Cajero"]
    w.writerow(header)
    for row in book.rows:
        by_rate = {t.rate: t for t in row.taxes}
        zero = row.voided
        cells = [row.date.strftime("%d/%m/%Y"), TYPE_LABELS[row.doc_type], row.document, row.customer or "",
                 row.identification or "", row.detail, METHOD_LABELS[row.method.value], row.reference or "",
                 "ANULADO" if row.voided else "Vigente"]
        for r in rates:
            t = by_rate.get(r)
            cells += [num(Decimal(0) if zero or not t else t.base), num(Decimal(0) if zero or not t else t.tax)]
        exempt = by_rate.get(Decimal("0.00"))
        cells += [num(Decimal(0) if zero or not exempt else exempt.base),
                  num(Decimal(0) if zero else row.subtotal), num(Decimal(0) if zero else row.tax_total),
                  num(Decimal(0) if zero else row.total), num(row.total if zero else Decimal(0)),
                  row.void_reason or "", row.cashier or ""]
        w.writerow(cells)
    # Fila de totales (sin anulados)
    by = {t.rate: t for t in s.by_rate}
    totals = ["TOTAL", "", "", "", "", f"{s.count} documentos", "", "", ""]
    for r in rates:
        t = by.get(r)
        totals += [num(t.base if t else 0), num(t.tax if t else 0)]
    ex = by.get(Decimal("0.00"))
    totals += [num(ex.base if ex else 0), num(s.subtotal), num(s.tax_total), num(s.total), num(s.voided_total), "", ""]
    w.writerow(totals)
    return ("﻿" + out.getvalue()).encode("utf-8")


def _table(data, widths, *, header=True, total_row=False, align_right_from=1, font=8):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", font),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font)]
    if total_row:
        style += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", font), ("BACKGROUND", (0, -1), (-1, -1), LIGHT)]
    t.setStyle(TableStyle(style))
    return t


def monthly_pdf(report: MonthlyReportOut, rows: List[SalesBookRowOut], gym: Gym, *, generated_on: date) -> bytes:
    buf = io.BytesIO()
    s = report.summary
    cur = s.currency
    m = lambda v: money(v, cur)  # noqa: E731
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceAfter=2, textColor=colors.black)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4, textColor=GOLD)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#555555"))
    normal = ParagraphStyle("n", parent=styles["Normal"], fontSize=9)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(15 * mm, 10 * mm, f"{gym.name} · Cierre {report.label} · generado el {generated_on:%d/%m/%Y}")
        canvas.drawRightString(doc.pagesize[0] - 15 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=18 * mm, title=f"Cierre mensual {report.label}", author=gym.name)
    story = [Paragraph(f"Cierre mensual — {report.label.capitalize()}", h1),
             Paragraph(gym.name, normal)]
    biz = business_line(gym.legal_name, gym.tax_id, gym.whatsapp_phone, gym.address)
    if biz:
        story.append(Paragraph(biz, small))
    if report.status == "cerrado":
        state = f"<b>CERRADO</b> el {report.closed_at:%d/%m/%Y}" + (f" por {report.closed_by_name}" if report.closed_by_name else "")
    else:
        state = "<b>PROVISIONAL</b> — el mes aún no tiene cierre; las cifras pueden cambiar"
    story += [Paragraph(f"Periodo: {report.date_from:%d/%m/%Y} al {report.date_to:%d/%m/%Y} · {state}", small)]
    if report.notes:
        story.append(Paragraph(f"Observaciones: {report.notes}", small))
    story.append(Paragraph("Montos en colones con IVA incluido; documentos anulados excluidos de los totales.", small))

    story += [Paragraph("Resumen", h2), _table([
        ["Documentos", "Base imponible", "IVA", "Total", "Anulados"],
        [str(s.count), m(s.subtotal), m(s.tax_total), m(s.total), f"{s.voided_count} · {m(s.voided_total)}"],
    ], [28 * mm, 38 * mm, 34 * mm, 38 * mm, 42 * mm], align_right_from=0)]

    rate_rows = [["Tarifa IVA", "Base", "IVA", "Total"]] + [
        ["Exento" if r.rate == 0 else f"{r.rate.normalize():f} %", m(r.base), m(r.tax), m(r.total)] for r in s.by_rate
    ] + [["Total", m(s.subtotal), m(s.tax_total), m(s.total)]]
    story += [Paragraph("IVA por tarifa", h2), _table(rate_rows, [40 * mm, 46 * mm, 46 * mm, 48 * mm], total_row=True)]

    type_rows = [["Tipo", "Documentos", "Base", "IVA", "Total"]] + [
        [TYPE_LABELS[t.doc_type], str(t.count), m(t.subtotal), m(t.tax_total), m(t.total)] for t in s.by_type
    ]
    method_rows = [["Método de pago", "Documentos", "Total"]] + [
        [METHOD_LABELS[x.method.value], str(x.count), m(x.total)] for x in s.by_method
    ]
    story += [Paragraph("Ingresos por tipo", h2), _table(type_rows, [36 * mm, 26 * mm, 40 * mm, 36 * mm, 42 * mm]),
              Paragraph("Ingresos por método de pago", h2), _table(method_rows, [60 * mm, 40 * mm, 80 * mm])]

    cs = s.cash_sessions
    story += [Paragraph("Arqueos de caja", h2), _table([
        ["Turnos", "Abiertos", "Esperado", "Contado", "Faltantes", "Sobrantes", "Neto"],
        [str(cs.count), str(cs.open_count), m(cs.expected_total), m(cs.counted_total), m(cs.shortages_total),
         m(cs.overages_total), m(cs.difference_total)],
    ], [16 * mm, 16 * mm, 30 * mm, 30 * mm, 28 * mm, 28 * mm, 32 * mm], align_right_from=0)]

    if s.by_day:
        day_rows = [["Fecha", "Membresías", "Tienda", "IVA", "Total"]] + [
            [d.date.strftime("%d/%m/%Y"), m(d.memberships), m(d.store), m(d.tax_total), m(d.total)] for d in s.by_day
        ] + [["Total", m(sum((d.memberships for d in s.by_day), Decimal(0))), m(sum((d.store for d in s.by_day), Decimal(0))),
              m(s.tax_total), m(s.total)]]
        story += [Paragraph("Detalle diario", h2), _table(day_rows, [30 * mm, 38 * mm, 38 * mm, 34 * mm, 40 * mm], total_row=True)]

    # Anexo: libro de ventas completo (horizontal)
    story += [PageBreak(), Paragraph(f"Anexo — Libro de ventas {report.label}", h1)]
    book = [["Fecha", "Documento", "Cliente", "Detalle", "Método", "Tarifa", "Base", "IVA", "Total", "Estado"]]
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7, leading=8.5)
    for r in rows:
        rates = ", ".join("Ex." if t.rate == 0 else f"{t.rate.normalize():f}%" for t in r.taxes)
        book.append([r.date.strftime("%d/%m/%Y"), r.document, Paragraph(r.customer or "—", cell),
                     Paragraph(r.detail, cell), METHOD_LABELS[r.method.value], rates, m(r.subtotal), m(r.tax_total),
                     m(r.total), "ANULADO" if r.voided else ""])
    if len(book) == 1:
        story.append(Paragraph("Sin movimientos en el periodo.", normal))
    else:
        t = _table(book, [15 * mm, 15 * mm, 24 * mm, 36 * mm, 15 * mm, 11 * mm, 18 * mm, 15 * mm, 19 * mm, 12 * mm],
                   align_right_from=6, font=7)
        story.append(t)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
