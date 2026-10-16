"""Utilidades sin BD: desglose de IVA y enlaces de WhatsApp."""
from decimal import Decimal

import pytest

from app.utils.money import q2, split_tax_included
from app.utils.whatsapp import money, normalize_phone, wa_link


@pytest.mark.parametrize("total,rate,base,tax", [
    ("1130", "13", "1000.00", "130.00"),
    ("1000", "13", "884.96", "115.04"),
    ("0.01", "13", "0.01", "0.00"),
    ("1500", "0", "1500.00", "0.00"),
    ("1040", "4", "1000.00", "40.00"),
])
def test_split_tax_included_cuadra_al_centimo(total, rate, base, tax):
    b, t = split_tax_included(Decimal(total), Decimal(rate))
    assert (str(b), str(t)) == (base, tax) and b + t == q2(Decimal(total))


@pytest.mark.parametrize("raw,expected", [
    ("8888-1234", "50688881234"), ("8888 1234", "50688881234"), ("+506 8888-1234", "50688881234"),
    ("50688881234", "50688881234"), ("00506 88881234", "50688881234"), ("+1 (305) 555-0100", "13055550100"),
    ("1234", None), ("", None), (None, None), ("abc", None), ("1234567890123456", None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_money_y_enlace():
    assert money(Decimal("25000"), "CRC") == "₡25 000,00"
    assert money(Decimal("1234567.5"), "USD") == "$1 234 567,50"
    assert money(Decimal("10"), "EUR") == "EUR 10,00"
    assert wa_link("50688881234", "Hola *Ana*\n¿Total? ₡1 000 & más") == (
        "https://wa.me/50688881234?text=Hola%20%2AAna%2A%0A%C2%BFTotal%3F%20%E2%82%A11%20000%20%26%20m%C3%A1s"
    )
