"""Aislamiento entre gimnasios: un gimnasio NUNCA ve ni modifica los datos de otro."""
import pytest

from app.dependencies.services import get_cedula_lookup_service
from app.main import app
from app.models.user import UserRole
from app.services.cedula_lookup_service import CedulaNotFound
from app.tests.conftest import headers_for, make_gym, make_user

M = "/api/v1/members"


@pytest.fixture
def gym_b(db):
    return make_gym(db, "gimnasio-b", "Gimnasio B")


@pytest.fixture
def admin_b(db, gym_b):
    return make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=gym_b)


@pytest.fixture
def h_admin_b(admin_b):
    return headers_for(admin_b)


def test_la_misma_cedula_puede_existir_en_dos_gimnasios(client, h_admin, h_admin_b):
    body = {"identification": "112345678", "first_name": "Ana", "last_name": "Mora"}
    assert client.post(M, json=body, headers=h_admin).status_code == 201
    assert client.post(M, json=body, headers=h_admin_b).status_code == 201     # otro gimnasio: permitido
    assert client.post(M, json=body, headers=h_admin_b).status_code == 409     # pero no dos veces en el MISMO


def test_un_gimnasio_no_ve_los_socios_de_otro(client, h_admin, h_admin_b, create_member):
    mine = create_member(first_name="Exclusivo", last_name="DelGimnasioA")
    assert client.get(f"{M}/{mine['id']}", headers=h_admin_b).status_code == 404
    assert client.get(M, headers=h_admin_b).json()["total"] == 0
    assert client.get(f"{M}?search=Exclusivo", headers=h_admin_b).json()["total"] == 0
    assert client.get(f"{M}?search=Exclusivo", headers=h_admin).json()["total"] == 1


def test_no_se_puede_modificar_ni_borrar_ni_restaurar_socios_ajenos(client, h_admin, h_admin_b, create_member):
    m = create_member()
    assert client.patch(f"{M}/{m['id']}", json={"first_name": "Hackeado"}, headers=h_admin_b).status_code == 404
    assert client.delete(f"{M}/{m['id']}", headers=h_admin_b).status_code == 404
    client.delete(f"{M}/{m['id']}", headers=h_admin)                      # el dueño lo da de baja
    assert client.post(f"{M}/{m['id']}/restore", headers=h_admin_b).status_code == 404
    assert client.get(f"{M}/{m['id']}", headers=h_admin).status_code == 404   # sigue de baja: B no pudo restaurarlo


def test_el_lookup_de_cedula_no_revela_socios_de_otro_gimnasio(client, h_admin_b, create_member):
    create_member(identification="112345678")                              # existe en el gimnasio A

    class Fake:
        calls = []

        def lookup(self, ident):
            Fake.calls.append(ident)
            raise CedulaNotFound("no está")

    app.dependency_overrides[get_cedula_lookup_service] = lambda: Fake()
    try:
        r = client.get(f"{M}/cedula-lookup/112345678", headers=h_admin_b)
    finally:
        app.dependency_overrides.pop(get_cedula_lookup_service, None)
    assert r.status_code == 404 and Fake.calls == ["112345678"]            # para B no es "ya registrado"


def test_planes_aislados_y_mismo_nombre_permitido(client, h_admin, h_admin_b):
    plan = {"name": "Mensual", "duration_days": 30, "price": "25000"}
    a = client.post("/api/v1/plans", json=plan, headers=h_admin)
    b = client.post("/api/v1/plans", json=plan, headers=h_admin_b)
    assert a.status_code == 201 and b.status_code == 201 and a.json()["id"] != b.json()["id"]
    assert [p["id"] for p in client.get("/api/v1/plans", headers=h_admin_b).json()] == [b.json()["id"]]
    pid = a.json()["id"]
    assert client.get(f"/api/v1/plans/{pid}", headers=h_admin_b).status_code == 404
    assert client.patch(f"/api/v1/plans/{pid}", json={"price": "1"}, headers=h_admin_b).status_code == 404
    assert client.delete(f"/api/v1/plans/{pid}", headers=h_admin_b).status_code == 404
    assert client.get(f"/api/v1/plans/{pid}", headers=h_admin).json()["price"] == "25000.00"   # intacto


def test_fichas_fisicas_aisladas(client, h_admin, h_admin_b, create_member):
    m = create_member()
    med = client.post(f"{M}/{m['id']}/measurements", json={"weight_kg": "80"}, headers=h_admin).json()
    base = f"{M}/{m['id']}/measurements"
    assert client.get(base, headers=h_admin_b).status_code == 404
    assert client.post(base, json={"weight_kg": "60"}, headers=h_admin_b).status_code == 404
    assert client.get(f"{base}/{med['id']}", headers=h_admin_b).status_code == 404
    assert client.patch(f"{base}/{med['id']}", json={"notes": "x"}, headers=h_admin_b).status_code == 404
    assert client.delete(f"{base}/{med['id']}", headers=h_admin_b).status_code == 404
    assert client.get(f"{base}/{med['id']}", headers=h_admin).status_code == 200


def test_los_usuarios_nuevos_nacen_en_el_gimnasio_de_quien_los_crea(client, db, h_admin_b, gym_b):
    r = client.post("/api/v1/auth/register", headers=h_admin_b, json={
        "full_name": "Nueva B", "email": "nueva-b@otro.com", "password": "Clave12345", "role": "receptionist"})
    assert r.status_code == 201 and r.json()["gym_id"] == str(gym_b.id)
    token = client.post("/api/v1/auth/login", json={"email": "nueva-b@otro.com", "password": "Clave12345"}).json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["gym_id"] == str(gym_b.id)
    assert client.get(M, headers={"Authorization": f"Bearer {token}"}).json()["total"] == 0   # no ve nada de A


def test_todo_lo_creado_por_b_queda_marcado_con_el_gimnasio_b(client, db, h_admin_b, gym_b):
    from sqlalchemy import text
    mid = client.post(M, json={"identification": "300000001", "first_name": "B", "last_name": "B"}, headers=h_admin_b).json()["id"]
    client.post(f"{M}/{mid}/measurements", json={"weight_kg": "70"}, headers=h_admin_b)
    client.post("/api/v1/plans", json={"name": "Solo B", "duration_days": 7, "price": "1"}, headers=h_admin_b)
    for table in ("members", "body_measurements", "plans"):
        gyms = {row[0] for row in db.execute(text(f"SELECT DISTINCT gym_id FROM {table}"))}
        assert gyms == {gym_b.id}, table


def test_el_gimnasio_se_toma_de_la_bd_y_no_del_token(client, db, gym_b, admin_b, create_member):
    """Un token con un 'gym_id' falso en sus claims no cambia el gimnasio efectivo."""
    from jose import jwt
    from app.core.config import settings
    m = create_member()                                                      # gimnasio A
    forged = jwt.encode({"sub": str(admin_b.id), "gym_id": "ignorado"}, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    assert client.get(f"{M}/{m['id']}", headers={"Authorization": f"Bearer {forged}"}).status_code == 404
