"""
Enlaces de WhatsApp «clic para chatear» (https://wa.me/<número>?text=<mensaje>).

No usan la API de Meta: abren WhatsApp Web o la app de la recepcionista con el mensaje
ya escrito, y ella lo envía. Sin costo, sin plantillas aprobadas y sin credenciales.
"""
import re
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional, Tuple
from urllib.parse import quote

from app.core.config import settings

_CURRENCY_SYMBOLS = {"CRC": "₡", "USD": "$"}


def normalize_phone(raw: Optional[str], default_country: Optional[str] = None) -> Optional[str]:
    """
    Número en formato internacional, solo dígitos (lo que exige wa.me), o None si no es válido.
      "8888-1234"        → "50688881234"   (8 dígitos: número local de Costa Rica)
      "+506 8888 1234"   → "50688881234"
      "+1 (305) 555-0100" → "13055550100"
    """
    if not raw:
        return None
    cc = default_country or settings.WHATSAPP_DEFAULT_COUNTRY_CODE
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("00"):
        digits = digits[2:]
    if len(digits) == 8:
        digits = f"{cc}{digits}"
    return digits if 10 <= len(digits) <= 15 else None


def wa_link(phone: str, message: str) -> str:
    return f"https://wa.me/{phone}?text={quote(message, safe='')}"


def money(amount: Decimal, currency: str) -> str:
    """"₡25 000,00" (formato de Costa Rica; en WhatsApp sí se puede usar el símbolo ₡)."""
    whole, _, frac = f"{Decimal(amount):.2f}".partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    symbol = _CURRENCY_SYMBOLS.get(currency)
    body = f"{' '.join(groups)},{frac}"
    return f"{sign}{symbol}{body}" if symbol else f"{sign}{currency} {body}"


def _d(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def sale_message(
    *, gym_name: str, currency: str, code: str, sale_date: date, customer: Optional[str],
    lines: Iterable[Tuple[int, str, Decimal]], subtotal: Decimal, taxes: Iterable[Tuple[Decimal, Decimal]],
    total: Decimal, method_label: str, reference: Optional[str], voided: bool, footer: Optional[str] = None,
) -> str:
    out = [f"*{gym_name}*", f"Comprobante de venta *{code}*", f"Fecha: {_d(sale_date)}"]
    if customer:
        out.append(f"Cliente: {customer}")
    if voided:
        out.append("⚠️ *VENTA ANULADA*")
    out.append("")
    for qty, name, line_total in lines:
        out.append(f"{qty} x {name} — {money(line_total, currency)}")
    out.append("")
    out.append(f"Subtotal: {money(subtotal, currency)}")
    for rate, amount in taxes:
        out.append(f"IVA ({rate.normalize():f} %): {money(amount, currency)}")
    out.append(f"*Total: {money(total, currency)}*")
    out.append(f"Pago: {method_label}" + (f" (Ref. {reference})" if reference else ""))
    out.append("")
    out.append(footer or "¡Gracias por su compra!")
    return "\n".join(out)


def payment_message(
    *, gym_name: str, currency: str, code: str, payment_date: date, member_name: str, plan_name: str,
    period_start: date, period_end: date, amount: Decimal, method_label: str, reference: Optional[str], voided: bool,
    footer: Optional[str] = None,
) -> str:
    out = [
        f"*{gym_name}*",
        f"Comprobante de pago *{code}*",
        f"Fecha: {_d(payment_date)}",
        "",
        f"Socio: {member_name}",
        f"Plan: {plan_name}",
        f"Vigencia: {_d(period_start)} al {_d(period_end)}",
        f"*Total pagado: {money(amount, currency)}*",
        f"Pago: {method_label}" + (f" (Ref. {reference})" if reference else ""),
    ]
    if voided:
        out.insert(3, "⚠️ *PAGO ANULADO*")
    out += ["", footer or "¡Gracias por entrenar con nosotros!"]
    return "\n".join(out)
