"""Seguridad de autenticación: register restringido, tokens inválidos y clave JWT."""
from datetime import timedelta

import pytest
from jose import jwt
from pydantic import ValidationError

from app.core.config import DEFAULT_JWT_SECRET, Settings, settings
from app.core.exceptions import ConflictException
from app.core.security import create_access_token
from app.models.user import UserRole
from app.scripts.create_admin import create_admin
from app.tests.conftest import PASSWORD, headers_for, make_user

NEW_USER = {"full_name": "Nueva Persona", "email": "nueva@lionfitness.com", "password": "OtraClave123", "role": "receptionist"}


# ── POST /auth/register: solo administradores ─────────────────────────────────
def test_register_sin_token_es_rechazado(raw_client):
    r = raw_client.post("/api/v1/auth/register", json=NEW_USER)
    assert r.status_code == 403 and r.json()["detail"] == "No autenticado. Inicie sesión para continuar"


@pytest.mark.parametrize("fixture", ["h_recep", "h_trainer", "h_socio"])
def test_register_rechaza_roles_no_admin(client, request, fixture):
    r = client.post("/api/v1/auth/register", json=NEW_USER, headers=request.getfixturevalue(fixture))
    assert r.status_code == 403
    assert r.json()["detail"] == "No tiene permisos para realizar esta acción"


def test_register_como_admin_crea_usuario_que_puede_iniciar_sesion(client, h_admin):
    r = client.post("/api/v1/auth/register", json=NEW_USER, headers=h_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "nueva@lionfitness.com" and body["role"] == "receptionist"
    assert "password" not in r.text and "password_hash" not in r.text

    login = client.post("/api/v1/auth/login", json={"email": "nueva@lionfitness.com", "password": "OtraClave123"})
    assert login.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["email"] == "nueva@lionfitness.com"


@pytest.mark.parametrize("role", ["admin", "receptionist", "trainer", "member"])
def test_admin_puede_crear_los_cuatro_roles(client, h_admin, role):
    r = client.post("/api/v1/auth/register", json={**NEW_USER, "email": f"{role}@example.com", "role": role}, headers=h_admin)
    assert r.status_code == 201 and r.json()["role"] == role


def test_register_correo_duplicado(client, h_admin):
    client.post("/api/v1/auth/register", json=NEW_USER, headers=h_admin)
    r = client.post("/api/v1/auth/register", json=NEW_USER, headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "user_exists"
    assert r.json()["detail"].startswith("Ya existe un usuario con el correo")


def test_register_validacion_en_espanol(client, h_admin):
    r = client.post("/api/v1/auth/register", json={**NEW_USER, "password": "corta"}, headers=h_admin)
    assert r.status_code == 422
    assert "Contraseña" in r.json()["detail"] and "Password must" not in r.text


# ── Login ─────────────────────────────────────────────────────────────────────
def test_login_credenciales_incorrectas(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "incorrecta"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Correo o contraseña incorrectos", "code": "invalid_credentials"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_login_usuario_inexistente_no_revela_que_no_existe(client):
    r = client.post("/api/v1/auth/login", json={"email": "nadie@lionfitness.com", "password": "loquesea"})
    assert r.status_code == 401 and r.json()["detail"] == "Correo o contraseña incorrectos"


def test_login_cuenta_deshabilitada(client, db):
    user = make_user(db, UserRole.RECEPTIONIST, "off@lionfitness.com", active=False)
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 401 and r.json()["code"] == "account_disabled"


def test_login_ok_y_me(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": admin.email, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200


# ── Tokens inválidos: deben ser 401 (antes eran HTTP 500) ─────────────────────
def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_token_basura_es_401_no_500(client):
    r = client.get("/api/v1/auth/me", headers=_bearer("esto-no-es-un-jwt"))
    assert r.status_code == 401
    assert r.json()["detail"] == "No se pudieron validar las credenciales"


def test_token_expirado_es_401(client, admin):
    token = create_access_token(subject=str(admin.id), expires_delta=timedelta(seconds=-5))
    assert client.get("/api/v1/auth/me", headers=_bearer(token)).status_code == 401


def test_token_firmado_con_otra_clave_es_401(client, admin):
    forged = jwt.encode({"sub": str(admin.id)}, "otra-clave-distinta", algorithm=settings.ALGORITHM)
    assert client.get("/api/v1/auth/me", headers=_bearer(forged)).status_code == 401


def test_token_sin_sub_o_con_sub_no_uuid_es_401(client):
    for claims in ({}, {"sub": "no-es-uuid"}, {"sub": ""}):
        token = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
        assert client.get("/api/v1/auth/me", headers=_bearer(token)).status_code == 401, claims


def test_token_de_usuario_deshabilitado_es_401(client, db):
    user = make_user(db, UserRole.ADMIN, "baja@lionfitness.com")
    headers = headers_for(user)
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_el_rol_se_lee_de_la_bd_no_del_token(client, db):
    """Un token emitido a un recepcionista no gana permisos aunque se le 'agregue' role=admin."""
    user = make_user(db, UserRole.RECEPTIONIST, "r@lionfitness.com")
    forged = jwt.encode({"sub": str(user.id), "role": "admin"}, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    r = client.post("/api/v1/auth/register", json=NEW_USER, headers=_bearer(forged))
    assert r.status_code == 403


# ── Clave JWT obligatoria fuera de desarrollo ─────────────────────────────────
def _settings(**kw):
    return Settings(_env_file=None, DATABASE_URL="postgresql://u:p@h/d", **kw)


@pytest.mark.parametrize(
    "secret",
    [DEFAULT_JWT_SECRET, "corta", "cambie-esto-por-una-clave-larga-y-aleatoria-de-al-menos-32-caracteres"],
)
def test_produccion_rechaza_claves_jwt_inseguras(secret):
    with pytest.raises(ValidationError) as exc:
        _settings(ENVIRONMENT="production", JWT_SECRET=secret)
    assert "JWT_SECRET" in str(exc.value)


def test_produccion_acepta_clave_fuerte_y_desarrollo_acepta_la_de_ejemplo():
    assert _settings(ENVIRONMENT="production", JWT_SECRET="x" * 48).ENVIRONMENT == "production"
    assert _settings(ENVIRONMENT="development", JWT_SECRET=DEFAULT_JWT_SECRET)
    with pytest.raises(ValidationError):  # un entorno desconocido NO se trata como desarrollo
        _settings(ENVIRONMENT="staging", JWT_SECRET=DEFAULT_JWT_SECRET)


# ── Script del primer administrador ───────────────────────────────────────────
def test_create_admin_crea_admin_con_hash(db):
    user = create_admin(db, email="Jefe@Lionfitness.com", full_name="Jefe Lion", password="ClaveSegura1")
    assert user.role == UserRole.ADMIN and user.email == "jefe@lionfitness.com"
    assert user.password_hash != "ClaveSegura1" and user.password_hash.startswith("$2")


def test_create_admin_rechaza_duplicado_y_clave_debil(db):
    create_admin(db, email="a@lionfitness.com", full_name="A", password="ClaveSegura1")
    with pytest.raises(ConflictException):
        create_admin(db, email="a@lionfitness.com", full_name="A", password="ClaveSegura1")
    with pytest.raises(ValidationError):
        create_admin(db, email="b@lionfitness.com", full_name="B", password="corta")


# ── Correos: sin distinguir mayúsculas ────────────────────────────────────────
def test_login_ignora_mayusculas_en_el_correo(client, admin):
    r = client.post("/api/v1/auth/login", json={"email": admin.email.upper().replace("@LIONFITNESS.COM", "@lionfitness.com"), "password": PASSWORD})
    assert r.status_code == 200


def test_login_encuentra_cuentas_antiguas_guardadas_con_mayusculas(client, db):
    """Compatibilidad: una cuenta creada en la Fase 1 como 'Kevin@...' sigue pudiendo entrar."""
    make_user(db, UserRole.ADMIN, "Kevin@Lionfitness.com")
    r = client.post("/api/v1/auth/login", json={"email": "kevin@lionfitness.com", "password": PASSWORD})
    assert r.status_code == 200


def test_register_no_permite_duplicados_que_solo_difieren_en_mayusculas(client, h_admin):
    client.post("/api/v1/auth/register", json=NEW_USER, headers=h_admin)
    r = client.post("/api/v1/auth/register", json={**NEW_USER, "email": "NUEVA@lionfitness.com"}, headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "user_exists"
