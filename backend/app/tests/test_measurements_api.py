"""Ficha física: IMC automático, historial evolutivo y reglas de edición."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

NO_EXISTE = "00000000-0000-0000-0000-000000000000"


def url(member_id, *parts):
    return "/".join(["/api/v1/members", str(member_id), "measurements", *map(str, parts)])


def _iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_crear_medicion_calcula_imc_y_categoria(client, h_trainer, trainer, create_member):
    m = create_member()
    r = client.post(url(m["id"]), headers=h_trainer, json={
        "weight_kg": "82.5", "height_cm": "180", "body_fat_pct": "18.5", "muscle_pct": "40", "waist_cm": "84"})
    assert r.status_code == 201
    b = r.json()
    assert b["bmi"] == "25.46" and b["bmi_category"] == "Sobrepeso"
    assert b["member_id"] == m["id"] and b["recorded_at"] and b["waist_cm"] == "84.00"


def test_el_cliente_no_puede_imponer_el_imc(client, h_trainer, create_member):
    m = create_member()
    r = client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": "82.5", "height_cm": "180", "bmi": "1.00"})
    assert r.json()["bmi"] == "25.46"


def test_sin_estatura_no_hay_imc(client, h_trainer, create_member):
    m = create_member()
    b = client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": "70"}).json()
    assert b["bmi"] is None and b["bmi_category"] is None


def test_se_registra_quien_hizo_la_medicion(client, db, h_trainer, trainer, create_member):
    from app.models.body_measurement import BodyMeasurement
    m = create_member()
    mid = client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": "70"}).json()["id"]
    assert db.get(BodyMeasurement, uuid.UUID(mid)).recorded_by_id == trainer.id


def test_historial_mas_reciente_primero(client, h_trainer, create_member):
    m = create_member()
    for dias, peso in [(60, "90"), (30, "85"), (0, "80")]:
        client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": peso, "height_cm": "180", "recorded_at": _iso(dias)})
    h = client.get(url(m["id"]), headers=h_trainer).json()
    assert h["member_id"] == m["id"] and h["total"] == 3
    assert [x["weight_kg"] for x in h["items"]] == ["80.00", "85.00", "90.00"]
    assert [x["bmi"] for x in h["items"]] == ["24.69", "26.23", "27.78"]  # evolución del IMC


def test_historial_paginado(client, h_trainer, create_member):
    m = create_member()
    for i in range(5):
        client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": str(70 + i), "recorded_at": _iso(10 - i)})
    h = client.get(url(m["id"]) + "?limit=2&offset=2", headers=h_trainer).json()
    assert h["total"] == 5 and len(h["items"]) == 2
    assert client.get(url(m["id"]) + "?limit=0", headers=h_trainer).status_code == 422


def test_historial_vacio(client, h_trainer, create_member):
    m = create_member()
    assert client.get(url(m["id"]), headers=h_trainer).json() == {"member_id": m["id"], "items": [], "total": 0}


# ── Reglas de validación ──────────────────────────────────────────────────────
@pytest.mark.parametrize("payload,fragmento", [
    ({}, "al menos una medida"),
    ({"weight_kg": "80", "body_fat_pct": "60", "muscle_pct": "50"}, "no puede superar 100"),
    ({"height_cm": "10"}, "Debe ser mayor o igual que 50"),
    ({"weight_kg": "75.123"}, "decimales"),
    ({"weight_kg": "abc"}, "número válido"),
])
def test_validaciones_en_espanol(client, h_trainer, create_member, payload, fragmento):
    m = create_member()
    r = client.post(url(m["id"]), headers=h_trainer, json=payload)
    assert r.status_code == 422 and fragmento in r.text


def test_fecha_futura_rechazada_y_fecha_sin_zona_aceptada(client, h_trainer, create_member):
    m = create_member()
    futura = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    r = client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": "70", "recorded_at": futura})
    assert r.status_code == 422 and r.json()["code"] == "measurement_in_future"
    ingenua = (datetime.now() - timedelta(days=1)).replace(tzinfo=None).isoformat()
    assert client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": "70", "recorded_at": ingenua}).status_code == 201


def test_socio_inexistente_o_dado_de_baja(client, h_trainer, h_admin, create_member):
    assert client.post(url(NO_EXISTE), headers=h_trainer, json={"weight_kg": "70"}).status_code == 404
    assert client.get(url(NO_EXISTE), headers=h_trainer).json()["code"] == "member_not_found"
    m = create_member()
    client.delete(f"/api/v1/members/{m['id']}", headers=h_admin)
    assert client.post(url(m["id"]), headers=h_trainer, json={"weight_kg": "70"}).status_code == 404
    assert client.get(url(m["id"]), headers=h_trainer).status_code == 404


# ── Edición ───────────────────────────────────────────────────────────────────
def _nueva(client, h, mid, **payload):
    return client.post(url(mid), headers=h, json=payload).json()


def test_editar_peso_recalcula_el_imc(client, h_trainer, create_member):
    m = create_member()
    med = _nueva(client, h_trainer, m["id"], weight_kg="82.5", height_cm="180")
    r = client.patch(url(m["id"], med["id"]), headers=h_trainer, json={"weight_kg": "72"})
    assert r.status_code == 200 and r.json()["bmi"] == "22.22" and r.json()["bmi_category"] == "Peso normal"
    assert r.json()["height_cm"] == "180.00"  # lo no enviado se conserva


def test_editar_no_permite_imponer_imc(client, h_trainer, create_member):
    m = create_member()
    med = _nueva(client, h_trainer, m["id"], weight_kg="82.5", height_cm="180")
    r = client.patch(url(m["id"], med["id"]), headers=h_trainer, json={"notes": "ok", "bmi": "1"})
    assert r.json()["bmi"] == "25.46" and r.json()["notes"] == "ok"


def test_quitar_la_estatura_deja_el_imc_en_nulo(client, h_trainer, create_member):
    m = create_member()
    med = _nueva(client, h_trainer, m["id"], weight_kg="82.5", height_cm="180")
    r = client.patch(url(m["id"], med["id"]), headers=h_trainer, json={"height_cm": None})
    assert r.status_code == 200 and r.json()["bmi"] is None and r.json()["weight_kg"] == "82.50"


def test_no_se_puede_vaciar_la_medicion(client, h_trainer, create_member):
    m = create_member()
    med = _nueva(client, h_trainer, m["id"], weight_kg="80")
    r = client.patch(url(m["id"], med["id"]), headers=h_trainer, json={"weight_kg": None})
    assert r.status_code == 422 and r.json()["code"] == "measurement_empty"
    # y el dato original sigue intacto
    assert client.get(url(m["id"], med["id"]), headers=h_trainer).json()["weight_kg"] == "80.00"


def test_la_composicion_se_valida_contra_lo_ya_guardado(client, h_trainer, create_member):
    m = create_member()
    med = _nueva(client, h_trainer, m["id"], body_fat_pct="30", muscle_pct="40")
    r = client.patch(url(m["id"], med["id"]), headers=h_trainer, json={"muscle_pct": "75"})
    assert r.status_code == 422 and r.json()["code"] == "composition_over_100"
    assert client.get(url(m["id"], med["id"]), headers=h_trainer).json()["muscle_pct"] == "40.00"


def test_no_hay_acceso_cruzado_entre_socios(client, h_trainer, create_member):
    a, b = create_member(), create_member()
    med = _nueva(client, h_trainer, a["id"], weight_kg="80")
    assert client.get(url(b["id"], med["id"]), headers=h_trainer).status_code == 404
    assert client.patch(url(b["id"], med["id"]), headers=h_trainer, json={"notes": "x"}).status_code == 404
    assert client.get(url(a["id"], med["id"]), headers=h_trainer).status_code == 200


def test_medicion_inexistente(client, h_trainer, create_member):
    m = create_member()
    r = client.get(url(m["id"], NO_EXISTE), headers=h_trainer)
    assert r.status_code == 404 and r.json() == {"detail": "Medición no encontrada", "code": "measurement_not_found"}


# ── Permisos ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("fixture,ok", [("h_admin", True), ("h_recep", True), ("h_trainer", True), ("h_socio", False)])
def test_quien_puede_registrar_y_consultar(client, request, create_member, fixture, ok):
    h, m = request.getfixturevalue(fixture), create_member()
    assert (client.post(url(m["id"]), headers=h, json={"weight_kg": "70"}).status_code == 201) is ok
    assert (client.get(url(m["id"]), headers=h).status_code == 200) is ok


def test_eliminar_medicion_solo_admin(client, h_admin, h_trainer, h_recep, create_member):
    m = create_member()
    med = _nueva(client, h_trainer, m["id"], weight_kg="80")
    assert client.delete(url(m["id"], med["id"]), headers=h_trainer).status_code == 403
    assert client.delete(url(m["id"], med["id"]), headers=h_recep).status_code == 403
    assert client.delete(url(m["id"], med["id"]), headers=h_admin).status_code == 204
    assert client.get(url(m["id"], med["id"]), headers=h_admin).status_code == 404


def test_al_borrar_un_socio_fisicamente_se_borra_su_historial(client, db, h_trainer, create_member):
    """El historial pertenece al socio (CASCADE); la baja lógica, en cambio, lo conserva."""
    from sqlalchemy import text
    m = create_member()
    _nueva(client, h_trainer, m["id"], weight_kg="80")
    db.execute(text("DELETE FROM members WHERE id = :i"), {"i": m["id"]})
    assert db.scalar(text("SELECT count(*) FROM body_measurements")) == 0
