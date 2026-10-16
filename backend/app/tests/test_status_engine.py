"""Reglas puras de vencimiento y morosidad (sin BD)."""
from datetime import date

import pytest

from app.models.enums import MemberStatus as S
from app.services.membership_status import days_remaining, describe_days, expiry_state, member_status_for

TODAY = date(2026, 10, 10)


@pytest.mark.parametrize("end,days,state", [
    (date(2026, 10, 30), 20, "vigente"),
    (date(2026, 10, 16), 6, "vigente"),        # justo fuera de la ventana de aviso (5)
    (date(2026, 10, 15), 5, "por_vencer"),     # primer día de la ventana
    (date(2026, 10, 11), 1, "por_vencer"),
    (date(2026, 10, 10), 0, "por_vencer"),     # hoy es el ÚLTIMO día con acceso
    (date(2026, 10, 9), -1, "vencida"),        # primer día de atraso
    (date(2026, 9, 10), -30, "vencida"),
])
def test_dias_restantes_y_estado(end, days, state):
    assert days_remaining(end, TODAY) == days
    assert expiry_state(end, TODAY, 5) == state


@pytest.mark.parametrize("end,grace,expected", [
    (date(2026, 10, 30), 0, S.ACTIVE),
    (date(2026, 10, 15), 0, S.EXPIRING_SOON),
    (date(2026, 10, 10), 0, S.EXPIRING_SOON),
    (date(2026, 10, 9), 0, S.EXPIRED),          # sin gracia: moroso desde el día siguiente
    (date(2026, 10, 9), 3, S.EXPIRING_SOON),    # con 3 días de gracia: aún no es moroso
    (date(2026, 10, 7), 3, S.EXPIRING_SOON),    # 3 días de atraso = límite de la gracia
    (date(2026, 10, 6), 3, S.EXPIRED),          # 4 días de atraso: moroso
])
def test_estado_del_socio(end, grace, expected):
    assert member_status_for(end, TODAY, 5, grace) == expected


def test_cambio_de_mes_y_de_anio():
    assert days_remaining(date(2027, 1, 7), date(2026, 12, 30)) == 8
    assert expiry_state(date(2026, 3, 1), date(2026, 2, 28), 5) == "por_vencer"   # 2026 no es bisiesto
    assert days_remaining(date(2028, 3, 1), date(2028, 2, 28)) == 2               # 2028 sí lo es


@pytest.mark.parametrize("d,text", [
    (30, "Vence en 30 días"), (2, "Vence en 2 días"), (1, "Vence mañana"), (0, "Vence hoy"),
    (-1, "Venció ayer"), (-2, "Venció hace 2 días"), (-45, "Venció hace 45 días"),
])
def test_textos_para_la_interfaz(d, text):
    assert describe_days(d) == text
