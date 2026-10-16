"""Traducción al español de los errores de validación y HTTP por defecto."""
from decimal import Decimal
from typing import Annotated, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.middleware.error_handler import _field_path, _label, translate_validation_error


class _Probe(BaseModel):
    text: Annotated[str, Field(min_length=3, max_length=5)]
    count: int
    ratio: Annotated[Decimal, Field(gt=0, le=10, max_digits=4, decimal_places=2)]
    flag: bool
    when: Optional[str] = None


def _errors(**payload):
    with pytest.raises(ValidationError) as exc:
        _Probe(**payload)
    return {e["loc"][0]: e for e in exc.value.errors()}


def test_campo_obligatorio():
    assert translate_validation_error(_errors()["text"]) == "Este campo es obligatorio"


def test_longitudes_de_texto():
    errs = _errors(text="a", count=1, ratio="1", flag=True)
    assert translate_validation_error(errs["text"]) == "Debe tener al menos 3 caracteres"
    errs = _errors(text="abcdefgh", count=1, ratio="1", flag=True)
    assert translate_validation_error(errs["text"]) == "No puede superar 5 caracteres"


def test_numeros_y_rangos():
    errs = _errors(text="abc", count="x", ratio="0", flag=True)
    assert translate_validation_error(errs["count"]) == "Debe ser un número entero"
    assert translate_validation_error(errs["ratio"]) == "Debe ser mayor que 0"
    errs = _errors(text="abc", count=1, ratio="11", flag=True)
    assert translate_validation_error(errs["ratio"]) == "Debe ser menor o igual que 10"


def test_decimales_y_booleanos():
    errs = _errors(text="abc", count=1, ratio="1.234", flag="quizas")
    assert "decimales" in translate_validation_error(errs["ratio"])
    assert translate_validation_error(errs["flag"]) == "Debe ser verdadero o falso"


def test_ningun_mensaje_por_defecto_en_ingles():
    """Barrido: ningún error típico debe salir con el texto original de Pydantic."""
    errs = _errors(text=1, count="z", ratio="abc", flag="zz")
    for err in errs.values():
        msg = translate_validation_error(err)
        assert not any(w in msg.lower() for w in ("should", "input", "valid integer", "field required"))


def test_value_error_propio_conserva_su_mensaje_en_espanol():
    err = {"type": "value_error", "msg": "Value error, La fecha de nacimiento no puede ser futura"}
    assert translate_validation_error(err) == "La fecha de nacimiento no puede ser futura"


def test_email_invalido():
    err = {"type": "value_error", "msg": "value is not a valid email address: An email address must have an @-sign."}
    assert translate_validation_error(err) == "Correo electrónico inválido"


@pytest.mark.parametrize(
    "etype,expected",
    [("uuid_parsing", "Identificador inválido"), ("json_invalid", "El cuerpo de la solicitud no es un JSON válido"),
     ("date_parsing", "Fecha inválida (use el formato AAAA-MM-DD)"), ("tipo_desconocido", "Valor inválido")],
)
def test_otros_tipos(etype, expected):
    assert translate_validation_error({"type": etype}) == expected


def test_enum_lista_valores_validos():
    msg = translate_validation_error({"type": "enum", "ctx": {"expected": "'activo', 'inactivo'"}})
    assert msg == "Valor no permitido. Valores válidos: 'activo', 'inactivo'"


def test_ruta_de_campo_y_etiquetas():
    assert _field_path(("body", "first_name")) == "first_name"
    assert _field_path(("body", "items", 2, "name")) == "items[2].name"
    assert _field_path(("query", "page")) == "page"
    assert _label("first_name") == "Nombre" and _label("weight_kg") == "Peso (kg)"
    assert _label("campo_raro") == "campo_raro" and _label("") == "Solicitud"


# ── A través de la API ────────────────────────────────────────────────────────
def test_sin_token_responde_en_espanol(raw_client):
    r = raw_client.get("/api/v1/members")
    assert r.status_code == 403
    assert r.json()["detail"] == "No autenticado. Inicie sesión para continuar"


def test_ruta_inexistente_en_espanol(raw_client):
    r = raw_client.get("/api/v1/no-existe")
    assert r.status_code == 404 and r.json()["detail"] == "Recurso no encontrado"


def test_metodo_no_permitido_en_espanol(raw_client):
    r = raw_client.delete("/api/v1/health")
    assert r.status_code == 405 and r.json()["detail"] == "Método no permitido"


def test_validacion_de_api_devuelve_detail_y_errors_en_espanol(client, h_admin):
    r = client.post("/api/v1/members", json={}, headers=h_admin)
    body = r.json()
    assert r.status_code == 422 and body["code"] == "validation_error"
    assert body["detail"].startswith("Datos inválidos. ")
    assert "Este campo es obligatorio" in body["detail"]
    assert {e["field"] for e in body["errors"]} == {"identification", "first_name", "last_name"}
    assert all(e["message"] == "Este campo es obligatorio" for e in body["errors"])
    assert "más" in body["detail"]  # "(y 2 errores más)"


def test_validacion_de_query_params_en_espanol(client, h_admin):
    r = client.get("/api/v1/members?page=0&size=500", headers=h_admin)
    assert r.status_code == 422
    msgs = {e["field"]: e["message"] for e in r.json()["errors"]}
    assert msgs["page"] == "Debe ser mayor o igual que 1"
    assert msgs["size"] == "Debe ser menor o igual que 100"


def test_uuid_invalido_en_ruta(client, h_admin):
    r = client.get("/api/v1/members/no-es-un-uuid", headers=h_admin)
    assert r.status_code == 422
    assert "Identificador inválido" in r.json()["detail"]


def test_json_malformado(client, h_admin):
    r = client.post("/api/v1/members", content="{esto no es json", headers={**h_admin, "Content-Type": "application/json"})
    assert r.status_code == 422
    assert "JSON válido" in r.json()["errors"][0]["message"]


def test_error_de_dominio_incluye_code(client, h_admin):
    r = client.get("/api/v1/members/00000000-0000-0000-0000-000000000000", headers=h_admin)
    assert r.status_code == 404
    assert r.json() == {"detail": "Socio no encontrado", "code": "member_not_found"}


def test_error_interno_no_filtra_detalles(client, monkeypatch, h_admin):
    from app.services.member_service import MemberService

    def boom(*a, **k):
        raise RuntimeError("secreto interno: password=1234")

    monkeypatch.setattr(MemberService, "list", boom)
    r = client.get("/api/v1/members", headers=h_admin)
    assert r.status_code == 500
    assert r.json() == {"detail": "Ocurrió un error inesperado. Intente de nuevo", "code": "internal_error"}
    assert "secreto" not in r.text
