"""Correcciones de la auditoría de noviembre 2026: sesión, login, usuarios, arranque y devoluciones."""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password, password_version
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.bootstrap import ensure_bootstrap_admin
from app.tests.conftest import PASSWORD, make_gym, make_user, open_cash

A = "/api/v1/auth"
U = "/api/v1/users"


def login(client, email, password=PASSWORD):
    return client.post(f"{A}/login", json={"email": email, "password": password})


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Sesión ────────────────────────────────────────────────────────────────────
def test_el_token_dura_un_turno_y_se_puede_renovar(client, admin):
    r = login(client, admin.email)
    assert r.status_code == 200
    body = r.json()
    assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 >= 8 * 3600
    claims = decode_access_token(body["access_token"])
    assert {"sub", "exp", "iat", "pwv", "sat"} <= set(claims)

    new = client.post(f"{A}/refresh", headers=bearer(body["access_token"]))
    assert new.status_code == 200
    renewed = decode_access_token(new.json()["access_token"])
    assert renewed["sat"] == claims["sat"]                 # la sesión conserva su inicio
    assert client.get(f"{A}/me", headers=bearer(new.json()["access_token"])).status_code == 200


def test_no_se_renueva_una_sesion_mas_alla_del_tope(client, admin):
    old_start = int(time.time()) - (settings.SESSION_MAX_HOURS + 1) * 3600
    token = create_access_token(str(admin.id), pwv=password_version(admin.password_hash), extra={"sat": old_start})
    r = client.post(f"{A}/refresh", headers=bearer(token))
    assert r.status_code == 401 and r.json()["code"] == "session_expired"


def test_un_token_sin_huella_de_contrasena_se_rechaza(client, admin):
    forged = jwt.encode({"sub": str(admin.id)}, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    assert client.get(f"{A}/me", headers=bearer(forged)).status_code == 401


# ── Fuerza bruta ──────────────────────────────────────────────────────────────
def test_el_login_se_bloquea_tras_varios_fallos(client, admin):
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        assert login(client, admin.email, "clave-equivocada").status_code == 401
    blocked = login(client, admin.email, PASSWORD)          # ni con la clave correcta, mientras dure el bloqueo
    assert blocked.status_code == 429 and blocked.json()["code"] == "too_many_attempts"
    assert "Demasiados intentos" in blocked.json()["detail"] and int(blocked.headers["Retry-After"]) > 0


def test_un_login_correcto_reinicia_el_contador(client, admin):
    for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
        login(client, admin.email, "clave-equivocada")
    assert login(client, admin.email).status_code == 200
    for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
        assert login(client, admin.email, "clave-equivocada").status_code == 401
    assert login(client, admin.email).status_code == 200


def test_el_bloqueo_tambien_aplica_a_correos_inexistentes(client):
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        login(client, "nadie@lionfitness.com", "x" * 8)
    assert login(client, "nadie@lionfitness.com", "x" * 8).status_code == 429


# ── Gestión de usuarios ───────────────────────────────────────────────────────
def test_admin_lista_desactiva_y_restablece_cuentas(client, db, h_admin, receptionist):
    items = client.get(U, headers=h_admin).json()["items"]
    assert {u["email"] for u in items} >= {"admin@lionfitness.com", "receptionist@lionfitness.com"}

    session = login(client, receptionist.email).json()["access_token"]
    off = client.patch(f"{U}/{receptionist.id}", json={"is_active": False}, headers=h_admin)
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert client.get(f"{A}/me", headers=bearer(session)).status_code == 401      # su sesión se corta al instante
    assert login(client, receptionist.email).json()["code"] == "account_disabled"

    client.patch(f"{U}/{receptionist.id}", json={"is_active": True}, headers=h_admin)
    reset = client.post(f"{U}/{receptionist.id}/password", json={"new_password": "NuevaClave2026"}, headers=h_admin)
    assert reset.status_code == 200
    assert login(client, receptionist.email).status_code == 401                   # la clave vieja ya no sirve
    assert login(client, receptionist.email, "NuevaClave2026").status_code == 200


def test_solo_el_admin_gestiona_usuarios(client, h_recep, h_trainer, admin):
    for h in (h_recep, h_trainer):
        assert client.get(U, headers=h).status_code == 403
        assert client.patch(f"{U}/{admin.id}", json={"is_active": False}, headers=h).status_code == 403


def test_el_admin_no_puede_bloquearse_a_si_mismo(client, h_admin, admin):
    r = client.patch(f"{U}/{admin.id}", json={"is_active": False}, headers=h_admin)
    assert r.status_code == 422 and r.json()["code"] == "cannot_demote_self"
    r = client.patch(f"{U}/{admin.id}", json={"role": "receptionist"}, headers=h_admin)
    assert r.status_code == 422 and r.json()["code"] == "cannot_demote_self"


def test_usuarios_de_otro_gimnasio_no_se_ven_ni_se_tocan(client, db, h_admin):
    other = make_user(db, UserRole.RECEPTIONIST, "ajena@otro.com", gym=make_gym(db, "otro-gym"))
    assert "ajena@otro.com" not in {u["email"] for u in client.get(U, headers=h_admin).json()["items"]}
    assert client.patch(f"{U}/{other.id}", json={"is_active": False}, headers=h_admin).status_code == 404


def test_cambiar_mi_contrasena_cierra_mis_otras_sesiones(client, receptionist):
    other_device = login(client, receptionist.email).json()["access_token"]
    mine = login(client, receptionist.email).json()["access_token"]
    wrong = client.post(f"{A}/me/password", json={"current_password": "mala-clave", "new_password": "OtraClave99"}, headers=bearer(mine))
    assert wrong.status_code == 422 and wrong.json()["code"] == "wrong_password"
    ok = client.post(f"{A}/me/password", json={"current_password": PASSWORD, "new_password": "OtraClave99"}, headers=bearer(mine))
    assert ok.status_code == 200
    assert client.get(f"{A}/me", headers=bearer(other_device)).status_code == 401
    assert client.get(f"{A}/me", headers=bearer(ok.json()["access_token"])).status_code == 200


# ── Administrador inicial (desarrollador) ────────────────────────────────────
def test_el_administrador_inicial_se_crea_una_sola_vez(db, client, monkeypatch):
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "Dev@Ejemplo.com")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "ClaveDev123")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_NAME", "Desarrollador")
    user = ensure_bootstrap_admin(db)
    assert user is not None and user.role == UserRole.ADMIN and user.email == "dev@ejemplo.com"
    assert login(client, "dev@ejemplo.com", "ClaveDev123").status_code == 200

    # Si luego cambia su contraseña, reiniciar la API NO la devuelve a la del .env.
    user.password_hash = hash_password("CambiadaDespues1")
    db.commit()
    again = ensure_bootstrap_admin(db)
    assert again.id == user.id
    assert db.query(User).filter(User.email == "dev@ejemplo.com").count() == 1
    assert login(client, "dev@ejemplo.com", "ClaveDev123").status_code == 401
    assert login(client, "dev@ejemplo.com", "CambiadaDespues1").status_code == 200


def test_sin_variables_no_se_crea_nada(db, monkeypatch):
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", None)
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", None)
    assert ensure_bootstrap_admin(db) is None


def test_contrasena_inicial_debil_no_crea_la_cuenta(db, monkeypatch):
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "debil@ejemplo.com")
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "123")
    assert ensure_bootstrap_admin(db) is None
    assert UserRepository(db).get_by_email("debil@ejemplo.com") is None


# ── Documentación de la API ───────────────────────────────────────────────────
def test_docs_ocultos_fuera_de_desarrollo(monkeypatch):
    from app.main import create_app
    monkeypatch.setattr(settings, "ENABLE_API_DOCS", False)
    with TestClient(create_app()) as c:
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
    monkeypatch.setattr(settings, "ENABLE_API_DOCS", True)
    with TestClient(create_app()) as c:
        assert c.get("/docs").status_code == 200


# ── Devoluciones de efectivo tras el cierre ──────────────────────────────────
@pytest.mark.cash_required
def test_anular_venta_de_caja_cerrada_registra_la_devolucion(client, clock, h_admin, h_recep, create_product):
    agua = create_product(name="Agua", price="1000", initial_stock=10)
    s = open_cash(client, h_recep, "10000")
    sale = client.post("/api/v1/sales", json={"items": [{"product_id": agua["id"], "quantity": 2}], "method": "efectivo"},
                       headers=h_recep).json()
    client.post(f"/api/v1/cash-sessions/{s['id']}/close", json={"counted_cash": "12000"}, headers=h_recep)

    r = client.post(f"/api/v1/sales/{sale['id']}/void", json={"reason": "Cliente devolvió"}, headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "cash_session_required_for_refund"
    stock = client.get(f"/api/v1/products/{agua['id']}", headers=h_admin).json()["stock"]
    assert stock == 8                                                        # nada cambió

    adm = open_cash(client, h_admin, "5000")
    assert client.post(f"/api/v1/sales/{sale['id']}/void", json={"reason": "Cliente devolvió"}, headers=h_admin).status_code == 200
    summary = client.get(f"/api/v1/cash-sessions/{adm['id']}", headers=h_admin).json()["summary"]
    assert summary["cash_refunds_total"] == "2000.00" and summary["expected_cash"] == "3000.00"


@pytest.mark.cash_required
def test_anular_en_la_misma_caja_abierta_no_es_devolucion(client, clock, h_admin, h_recep, create_product):
    agua = create_product(name="Agua", price="1000", initial_stock=10)
    s = open_cash(client, h_recep, "10000")
    sale = client.post("/api/v1/sales", json={"items": [{"product_id": agua["id"], "quantity": 2}], "method": "efectivo"},
                       headers=h_recep).json()
    assert client.post(f"/api/v1/sales/{sale['id']}/void", json={"reason": "Error"}, headers=h_admin).status_code == 200
    summary = client.get(f"/api/v1/cash-sessions/{s['id']}", headers=h_admin).json()["summary"]
    assert summary["cash_refunds_total"] == "0.00" and summary["expected_cash"] == "10000.00"


@pytest.mark.cash_required
def test_anular_sinpe_de_caja_cerrada_no_exige_caja(client, clock, h_admin, h_recep, create_member, plan):
    s = open_cash(client, h_recep, "0")
    p = client.post("/api/v1/payments", json={"member_id": create_member()["id"], "plan_id": plan["id"],
                                               "method": "sinpe", "reference": "SP-1"}, headers=h_recep).json()
    client.post(f"/api/v1/cash-sessions/{s['id']}/close", json={"counted_cash": "0"}, headers=h_recep)
    assert client.post(f"/api/v1/payments/{p['id']}/void", json={"reason": "SINPE devuelto"}, headers=h_admin).status_code == 200


# ── Estados al día sin depender del job ───────────────────────────────────────
def test_el_panel_recalcula_los_estados_del_dia(client, clock, h_admin, create_member, plan):
    m = create_member()
    client.post("/api/v1/payments", json={"member_id": m["id"], "plan_id": plan["id"], "method": "efectivo"}, headers=h_admin)
    assert client.get(f"/api/v1/members/{m['id']}", headers=h_admin).json()["status"] == "activo"
    clock.advance(days=40)                      # venció hace 10 días y nadie corrió el job
    d = client.get("/api/v1/dashboard", headers=h_admin).json()
    assert d["members_overdue"] == 1 and d["members_active"] == 0
    assert client.get(f"/api/v1/members/{m['id']}", headers=h_admin).json()["status"] == "moroso"
