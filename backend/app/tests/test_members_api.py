"""API de socios: CRUD, permisos por rol, búsqueda, paginación, baja lógica."""
import uuid

import pytest

BASE = "/api/v1/members"
NO_EXISTE = "00000000-0000-0000-0000-000000000000"


# ── Altas ─────────────────────────────────────────────────────────────────────
def test_crear_socio_normaliza_y_aplica_valores_por_defecto(client, h_recep):
    r = client.post(BASE, headers=h_recep, json={
        "identification": "1-1234-5678", "first_name": " Ana ", "last_name": "Mora",
        "phone": "8888-1234", "email": "ana@example.com", "gender": "femenino", "birth_date": "1995-04-12",
    })
    assert r.status_code == 201
    m = r.json()
    assert m["identification"] == "112345678" and m["first_name"] == "Ana"
    assert m["full_name"] == "Ana Mora" and m["phone"] == "88881234"
    # Alta SIN cobro: nace inactivo hasta su primer pago (nunca activo sin membresía).
    assert m["status"] == "inactivo" and m["joined_at"] and uuid.UUID(m["id"])


def test_cedula_duplicada_aunque_venga_con_guiones(client, h_admin, create_member):
    create_member(identification="112345678")
    r = client.post(BASE, headers=h_admin, json={"identification": "1-1234-5678", "first_name": "X", "last_name": "Y"})
    assert r.status_code == 409 and r.json()["code"] == "member_exists"
    assert "112345678" in r.json()["detail"]


def test_datos_invalidos_devuelven_422_en_espanol(client, h_admin):
    r = client.post(BASE, headers=h_admin, json={
        "identification": "12", "first_name": "  ", "last_name": "Mora", "birth_date": "2999-01-01"})
    assert r.status_code == 422
    msgs = {e["field"]: e["message"] for e in r.json()["errors"]}
    assert "identificación" in msgs["identification"].lower()
    assert msgs["first_name"] == "Este campo no puede estar vacío"
    assert msgs["birth_date"] == "La fecha de nacimiento no puede ser futura"


# ── Matriz de permisos ────────────────────────────────────────────────────────
@pytest.mark.parametrize("fixture,can_read,can_write,can_delete", [
    ("h_admin", True, True, True),
    ("h_recep", True, True, False),
    ("h_trainer", True, False, False),
    ("h_socio", False, False, False),
])
def test_permisos_por_rol(client, request, h_admin, create_member, fixture, can_read, can_write, can_delete):
    h = request.getfixturevalue(fixture)
    m = create_member()
    mid = m["id"]

    assert (client.get(BASE, headers=h).status_code == 200) is can_read
    assert (client.get(f"{BASE}/{mid}", headers=h).status_code == 200) is can_read

    created = client.post(BASE, headers=h, json={"identification": "999888777", "first_name": "N", "last_name": "M"})
    assert (created.status_code == 201) is can_write
    assert (client.patch(f"{BASE}/{mid}", headers=h, json={"notes": "x"}).status_code == 200) is can_write

    assert (client.delete(f"{BASE}/{mid}", headers=h).status_code == 204) is can_delete
    if not can_delete:
        restore_status = client.post(f"{BASE}/{mid}/restore", headers=h).status_code
        assert restore_status == 403


def test_sin_autenticar_no_hay_acceso(raw_client):
    for method, url in [("get", BASE), ("post", BASE), ("get", f"{BASE}/{NO_EXISTE}"), ("delete", f"{BASE}/{NO_EXISTE}")]:
        assert getattr(raw_client, method)(url).status_code == 403


# ── Lectura y edición ─────────────────────────────────────────────────────────
def test_detalle_y_404(client, h_recep, create_member):
    m = create_member(first_name="Luis")
    assert client.get(f"{BASE}/{m['id']}", headers=h_recep).json()["first_name"] == "Luis"
    r = client.get(f"{BASE}/{NO_EXISTE}", headers=h_recep)
    assert r.status_code == 404 and r.json()["code"] == "member_not_found"


def test_actualizacion_parcial_no_toca_la_cedula(client, h_recep, create_member):
    m = create_member(identification="111222333", last_name="Mora")
    r = client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={
        "first_name": "Luisa", "identification": "999999999", "phone": "8000-0000"})
    assert r.status_code == 200
    body = r.json()
    assert body["first_name"] == "Luisa" and body["last_name"] == "Mora" and body["phone"] == "80000000"
    assert body["identification"] == "111222333"  # no editable


def test_actualizacion_puede_limpiar_campos_opcionales(client, h_recep, create_member):
    m = create_member(phone="88881234", notes="nota")
    r = client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={"phone": None, "notes": None})
    assert r.json()["phone"] is None and r.json()["notes"] is None


def test_no_se_puede_dejar_nombre_nulo(client, h_recep, create_member):
    m = create_member()
    r = client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={"first_name": None})
    assert r.status_code == 422 and "no puede ser nulo" in r.json()["detail"]


def test_solo_se_alterna_activo_inactivo_a_mano(client, clock, h_recep, create_member, plan):
    m = create_member()
    sin_pago = client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={"status": "activo"})
    assert sin_pago.status_code == 422 and sin_pago.json()["code"] == "membership_required"
    client.post("/api/v1/payments", json={"member_id": m["id"], "plan_id": plan["id"], "method": "efectivo"}, headers=h_recep)
    for estado in ("moroso", "por_vencer"):
        r = client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={"status": estado})
        assert r.status_code == 422 and r.json()["code"] == "status_not_manual"
    r = client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={"status": "inactivo"})
    assert r.status_code == 200 and r.json()["status"] == "inactivo"
    assert client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={"status": "activo"}).json()["status"] == "activo"
    bad = client.patch(f"{BASE}/{m['id']}", headers=h_recep, json={"status": "volando"})
    assert bad.status_code == 422 and "Valores válidos" in bad.json()["errors"][0]["message"]


# ── Baja lógica y restauración ────────────────────────────────────────────────
def test_baja_logica_oculta_al_socio_y_bloquea_la_cedula(client, h_admin, h_recep, create_member):
    m = create_member(identification="555666777")
    assert client.delete(f"{BASE}/{m['id']}", headers=h_admin).status_code == 204

    assert client.get(f"{BASE}/{m['id']}", headers=h_admin).status_code == 404
    assert m["id"] not in [x["id"] for x in client.get(BASE, headers=h_admin).json()["items"]]
    assert client.delete(f"{BASE}/{m['id']}", headers=h_admin).status_code == 404  # ya no existe

    r = client.post(BASE, headers=h_recep, json={"identification": "555666777", "first_name": "Otro", "last_name": "Socio"})
    assert r.status_code == 409 and r.json()["code"] == "member_deleted"
    assert "restaure" in r.json()["detail"]


def test_restaurar_deja_al_socio_inactivo(client, h_admin, create_member):
    m = create_member()
    client.delete(f"{BASE}/{m['id']}", headers=h_admin)
    r = client.post(f"{BASE}/{m['id']}/restore", headers=h_admin)
    assert r.status_code == 200 and r.json()["status"] == "inactivo"
    assert client.get(f"{BASE}/{m['id']}", headers=h_admin).status_code == 200


def test_restaurar_un_socio_que_no_esta_de_baja(client, h_admin, create_member):
    m = create_member()
    r = client.post(f"{BASE}/{m['id']}/restore", headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "member_not_deleted"
    assert client.post(f"{BASE}/{NO_EXISTE}/restore", headers=h_admin).status_code == 404


# ── Búsqueda, filtros y paginación ────────────────────────────────────────────
def _names(resp):
    return [f"{m['first_name']} {m['last_name']}" for m in resp.json()["items"]]


def test_busqueda_ignora_tildes_y_mayusculas(client, h_recep, create_member):
    create_member(first_name="José", last_name="Muñoz")
    create_member(first_name="Ana", last_name="Mora")
    assert _names(client.get(f"{BASE}?search=jose", headers=h_recep)) == ["José Muñoz"]
    assert _names(client.get(f"{BASE}?search=MUNOZ", headers=h_recep)) == ["José Muñoz"]
    assert _names(client.get(f"{BASE}?search=Muñoz", headers=h_recep)) == ["José Muñoz"]


def test_busqueda_por_varias_palabras_y_por_cedula(client, h_recep, create_member):
    create_member(first_name="Ana María", last_name="Mora Solano", identification="112345678")
    create_member(first_name="Ana", last_name="Pérez", identification="900000001")
    assert _names(client.get(f"{BASE}?search=ana mora", headers=h_recep)) == ["Ana María Mora Solano"]
    assert _names(client.get(f"{BASE}?search=1-1234-5678", headers=h_recep)) == ["Ana María Mora Solano"]
    assert _names(client.get(f"{BASE}?search=9000", headers=h_recep)) == ["Ana Pérez"]
    assert client.get(f"{BASE}?search=ana zzz", headers=h_recep).json()["total"] == 0


@pytest.mark.parametrize("texto", ["%", "_", "\\", "a%", "%%"])
def test_busqueda_trata_comodines_como_texto_literal(client, h_recep, create_member, texto):
    create_member(first_name="Ana", last_name="Mora")
    assert client.get(f"{BASE}", params={"search": texto}, headers=h_recep).json()["total"] == 0


def test_filtro_por_estado(client, clock, h_recep, create_member, plan):
    a = create_member(first_name="Activo")
    b = create_member(first_name="Inactivo")
    client.post("/api/v1/payments", json={"member_id": a["id"], "plan_id": plan["id"], "method": "efectivo"}, headers=h_recep)
    assert _names(client.get(f"{BASE}?status=inactivo", headers=h_recep)) == ["Inactivo Mora"]
    assert _names(client.get(f"{BASE}?status=activo", headers=h_recep)) == ["Activo Mora"]
    assert client.get(f"{BASE}?status=moroso", headers=h_recep).json()["total"] == 0
    assert a["id"]


def test_paginacion(client, h_recep, create_member):
    for i in range(5):
        create_member(first_name=f"N{i}", last_name=f"Apellido{i}")
    p1 = client.get(f"{BASE}?size=2&page=1", headers=h_recep).json()
    p3 = client.get(f"{BASE}?size=2&page=3", headers=h_recep).json()
    p9 = client.get(f"{BASE}?size=2&page=9", headers=h_recep).json()
    assert (p1["total"], p1["pages"], p1["page"], p1["size"], len(p1["items"])) == (5, 3, 1, 2, 2)
    assert len(p3["items"]) == 1 and p9["items"] == [] and p9["total"] == 5
    # orden estable por apellido, nombre
    allnames = [m["last_name"] for m in client.get(f"{BASE}?size=100", headers=h_recep).json()["items"]]
    assert allnames == sorted(allnames)


def test_lista_vacia(client, h_recep):
    assert client.get(BASE, headers=h_recep).json() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}
