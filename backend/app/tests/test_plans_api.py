"""API de planes: edición dinámica (sin valores fijos) y reglas de integridad."""
from datetime import date, timedelta

import pytest

from app.models.membership import Membership

BASE = "/api/v1/plans"
MENSUAL = {"name": "Mensual", "duration_days": 30, "price": "25000.00", "description": "Acceso total"}


def _crear(client, h, **over):
    r = client.post(BASE, headers=h, json={**MENSUAL, **over})
    assert r.status_code == 201, r.text
    return r.json()


def test_admin_crea_y_lee_un_plan(client, h_admin):
    p = _crear(client, h_admin)
    assert p["name"] == "Mensual" and p["duration_days"] == 30 and p["price"] == "25000.00"
    assert p["is_active"] is True and p["description"] == "Acceso total"
    assert client.get(f"{BASE}/{p['id']}", headers=h_admin).json()["id"] == p["id"]


@pytest.mark.parametrize("fixture,lista,crea", [
    ("h_admin", 200, 201), ("h_recep", 200, 403), ("h_trainer", 403, 403), ("h_socio", 403, 403)])
def test_permisos(client, request, fixture, lista, crea):
    h = request.getfixturevalue(fixture)
    assert client.get(BASE, headers=h).status_code == lista
    assert client.post(BASE, headers=h, json=MENSUAL).status_code == crea


def test_recepcionista_no_puede_editar_ni_borrar(client, h_admin, h_recep):
    p = _crear(client, h_admin)
    assert client.patch(f"{BASE}/{p['id']}", headers=h_recep, json={"price": "1"}).status_code == 403
    assert client.delete(f"{BASE}/{p['id']}", headers=h_recep).status_code == 403
    assert client.get(f"{BASE}/{p['id']}", headers=h_recep).status_code == 200  # sí puede consultar


def test_nombre_unico_sin_distinguir_mayusculas(client, h_admin):
    _crear(client, h_admin)
    r = client.post(BASE, headers=h_admin, json={**MENSUAL, "name": "  mensual "})
    assert r.status_code == 409 and r.json()["code"] == "plan_name_taken"


def test_editar_precio_y_duracion_sin_tocar_lo_demas(client, h_admin):
    p = _crear(client, h_admin)
    r = client.patch(f"{BASE}/{p['id']}", headers=h_admin, json={"price": "27500.50", "duration_days": 31})
    b = r.json()
    assert r.status_code == 200 and b["price"] == "27500.50" and b["duration_days"] == 31
    assert b["name"] == "Mensual" and b["description"] == "Acceso total" and b["is_active"] is True


def test_renombrar_a_su_propio_nombre_es_valido_pero_a_otro_existente_no(client, h_admin):
    a, b = _crear(client, h_admin), _crear(client, h_admin, name="Trimestral", duration_days=90)
    assert client.patch(f"{BASE}/{a['id']}", headers=h_admin, json={"name": "MENSUAL"}).status_code == 200
    r = client.patch(f"{BASE}/{b['id']}", headers=h_admin, json={"name": "mensual"})
    assert r.status_code == 409 and r.json()["code"] == "plan_name_taken"


def test_desactivar_y_filtrar_activos(client, h_admin, h_recep):
    a, b = _crear(client, h_admin), _crear(client, h_admin, name="Anual", duration_days=365)
    client.patch(f"{BASE}/{b['id']}", headers=h_admin, json={"is_active": False})
    todos = client.get(BASE, headers=h_recep).json()
    activos = client.get(f"{BASE}?active_only=true", headers=h_recep).json()
    assert len(todos) == 2 and [p["name"] for p in activos] == ["Mensual"] and a["id"]


def test_lista_ordenada_por_duracion(client, h_admin):
    _crear(client, h_admin, name="Anual", duration_days=365)
    _crear(client, h_admin, name="Mensual", duration_days=30)
    _crear(client, h_admin, name="Semestral", duration_days=180)
    assert [p["name"] for p in client.get(BASE, headers=h_admin).json()] == ["Mensual", "Semestral", "Anual"]


@pytest.mark.parametrize("payload,campo", [
    ({"price": "-5"}, "price"), ({"duration_days": 0}, "duration_days"),
    ({"name": "X"}, "name"), ({"price": "10.999"}, "price"), ({"duration_days": "abc"}, "duration_days")])
def test_validaciones_en_espanol(client, h_admin, payload, campo):
    r = client.post(BASE, headers=h_admin, json={**MENSUAL, **payload})
    assert r.status_code == 422
    err = next(e for e in r.json()["errors"] if e["field"] == campo)
    assert not any(w in err["message"].lower() for w in ("should", "input", "string", "greater than or equal"))


def test_no_se_puede_poner_campos_obligatorios_en_nulo(client, h_admin):
    p = _crear(client, h_admin)
    for campo in ("name", "price", "duration_days", "is_active"):
        r = client.patch(f"{BASE}/{p['id']}", headers=h_admin, json={campo: None})
        assert r.status_code == 422, campo


def test_eliminar_plan_sin_membresias(client, h_admin):
    p = _crear(client, h_admin)
    assert client.delete(f"{BASE}/{p['id']}", headers=h_admin).status_code == 204
    assert client.get(f"{BASE}/{p['id']}", headers=h_admin).status_code == 404


def test_no_se_elimina_un_plan_con_membresias(client, db, h_admin, create_member):
    import uuid
    p = _crear(client, h_admin)
    m = create_member()
    from app.tests.conftest import default_gym
    db.add(Membership(gym_id=default_gym(db).id, member_id=uuid.UUID(m["id"]), plan_id=uuid.UUID(p["id"]),
                      start_date=date.today(), end_date=date.today() + timedelta(days=30)))
    db.commit()
    r = client.delete(f"{BASE}/{p['id']}", headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "plan_in_use"
    assert client.get(f"{BASE}/{p['id']}", headers=h_admin).status_code == 200  # sigue existiendo
    # la alternativa correcta: desactivarlo
    assert client.patch(f"{BASE}/{p['id']}", headers=h_admin, json={"is_active": False}).json()["is_active"] is False
