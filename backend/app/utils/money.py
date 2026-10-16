"""Redondeo y desglose de impuestos con Decimal (nunca float para dinero)."""
from decimal import ROUND_HALF_UP, Decimal
from typing import Tuple

CENT = Decimal("0.01")


def q2(value: Decimal) -> Decimal:
    """Redondeo comercial a 2 decimales (0,005 → 0,01)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def split_tax_included(total: Decimal, rate_pct: Decimal) -> Tuple[Decimal, Decimal]:
    """
    Desglosa un monto con IVA INCLUIDO: devuelve (base, impuesto) con base + impuesto == total
    exacto al céntimo. Ej.: 1130,00 al 13 % → (1000,00, 130,00).
    """
    total = q2(total)
    rate = Decimal(rate_pct)
    if rate <= 0:
        return total, Decimal("0.00")
    base = q2(total / (Decimal(1) + rate / Decimal(100)))
    return base, total - base
