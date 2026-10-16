"""Tests de esquemas y utilidades de la Fase 2 (no requieren base de datos)."""
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.schemas.body_measurement import BodyMeasurementCreate, BodyMeasurementUpdate
from app.schemas.member import MemberCreate, MemberUpdate
from app.schemas.plan import PlanCreate, PlanUpdate
from app.utils.anthropometrics import calculate_bmi, classify_bmi


# ── IMC ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "peso,estatura,esperado",
    [("75", "175", "24.49"), ("82.5", "180", "25.46"), ("50", "160", "19.53")],
)
def test_calculate_bmi(peso, estatura, esperado):
    assert calculate_bmi(D(peso), D(estatura)) == D(esperado)


@pytest.mark.parametrize("peso,estatura", [(None, "175"), ("75", None), ("75", "0"), ("0", "175")])
def test_calculate_bmi_datos_invalidos_devuelve_none(peso, estatura):
    assert calculate_bmi(D(peso) if peso else None, D(estatura) if estatura else None) is None


@pytest.mark.parametrize(
    "imc,categoria",
    [("17", "Bajo peso"), ("22", "Peso normal"), ("27", "Sobrepeso"),
     ("32", "Obesidad grado I"), ("37", "Obesidad grado II"), ("41", "Obesidad grado III")],
)
def test_classify_bmi(imc, categoria):
    assert classify_bmi(D(imc)) == categoria


def test_bmi_se_calcula_en_el_schema_y_entra_en_model_dump():
    m = BodyMeasurementCreate(weight_kg="82.5", height_cm="180")
    assert m.bmi == D("25.46")
    assert m.model_dump()["bmi"] == D("25.46")


def test_bmi_no_es_un_campo_de_entrada():
    """Aunque el cliente envíe 'bmi', se ignora: siempre se recalcula."""
    m = BodyMeasurementCreate(weight_kg="82.5", height_cm="180", bmi="1")
    assert m.bmi == D("25.46")


def test_medicion_sin_estatura_no_tiene_bmi():
    assert BodyMeasurementCreate(weight_kg="70").bmi is None


@pytest.mark.parametrize(
    "payload",
    [
        {},                                                                # ninguna medida
        {"weight_kg": "80", "body_fat_pct": "60", "muscle_pct": "50"},      # grasa + músculo > 100
        {"height_cm": "10"},                                               # estatura imposible
        {"weight_kg": "75.123"},                                           # demasiados decimales
    ],
)
def test_medicion_invalida(payload):
    with pytest.raises(ValidationError):
        BodyMeasurementCreate(**payload)


def test_update_de_medicion_es_parcial():
    assert BodyMeasurementUpdate(weight_kg="80").model_dump(exclude_unset=True) == {"weight_kg": D("80")}


# ── Miembros ──────────────────────────────────────────────────────────────────
def test_member_normaliza_cedula_telefono_y_nombre():
    m = MemberCreate(identification="1-1234-5678", first_name=" Ana ", last_name="Mora", phone="8888-1234")
    assert (m.identification, m.phone, m.first_name) == ("112345678", "88881234", "Ana")


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(identification="12", first_name="A", last_name="B"),
        dict(identification="112345678", first_name="  ", last_name="B"),
        dict(identification="112345678", first_name="A", last_name="B", birth_date="2999-01-01"),
        dict(identification="112345678", first_name="A", last_name="B", phone="abc"),
    ],
)
def test_member_invalido(kwargs):
    with pytest.raises(ValidationError):
        MemberCreate(**kwargs)


def test_mensajes_de_validacion_de_member_estan_en_espanol():
    with pytest.raises(ValidationError) as exc:
        MemberCreate(identification="12", first_name="", last_name="B")
    msgs = " ".join(e["msg"] for e in exc.value.errors())
    assert "La identificación" in msgs and "no puede estar vacío" in msgs


def test_member_update_no_permite_cambiar_cedula():
    assert "identification" not in MemberUpdate.model_fields
    assert MemberUpdate(first_name="Luisa").model_dump(exclude_unset=True) == {"first_name": "Luisa"}


# ── Planes ────────────────────────────────────────────────────────────────────
def test_plan_valido_y_activo_por_defecto():
    p = PlanCreate(name="Mensual", duration_days=30, price="25000")
    assert p.price == D("25000") and p.is_active is True


@pytest.mark.parametrize(
    "kwargs",
    [dict(name="X", duration_days=30, price="1"), dict(name="Mensual", duration_days=0, price="1"),
     dict(name="Mensual", duration_days=30, price="-1"), dict(name="Mensual", duration_days=30, price="10.999")],
)
def test_plan_invalido(kwargs):
    with pytest.raises(ValidationError):
        PlanCreate(**kwargs)


def test_plan_update_parcial():
    assert PlanUpdate(price="30000").model_dump(exclude_unset=True) == {"price": D("30000")}
