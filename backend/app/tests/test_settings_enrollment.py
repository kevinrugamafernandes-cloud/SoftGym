"""Configuración del negocio, IVA de planes e inscripción con cobro obligatorio."""
import pytest
from sqlalchemy import text

from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user, open_cash

ST = "/api/v1/settings"
EN = "/api/v1/members/enroll"


# ── Configuración ─────────────────────────────────────────────────────────────
def test_configuracion_por_defecto_y_edicion(client, h_admin, h_recep, h_trainer):
    s = client.get(ST, headers=h_recep).json()
    assert s["name"] == "Lion Fitness Center" and "{nombre}" in s["overdue_message"]
    assert "fecha_vencimiento" in s["placeholders"]
    r = client.patch(ST, json={
        "name": "  Lion  Fitness Center Heredia ", "whatsapp_phone": "8888-1234", "tax_id": "3-101-123456",
        "address": "100 m norte de la iglesia", "legal_name": "Lion Fitness S.A.",
        "overdue_message": "Hola {nombre}, tu plan {plan} venció el {fecha_vencimiento}.",
        "receipt_message": "¡Nos vemos en el gym!",
    }, headers=h_admin)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["name"] == "Lion Fitness Center Heredia" and s["tax_id"] == "3101123456" and s["whatsapp_phone"] == "88881234"
    assert client.patch(ST, json={"name": "X"}, headers=h_recep).status_code == 403
    assert client.get(ST, headers=h_trainer).status_code == 200


def test_validaciones_de_configuracion(client, h_admin):
    bad = client.patch(ST, json={"overdue_message": "Hola {cliente}"}, headers=h_admin)
    assert bad.status_code == 422 and "Variable desconocida: {cliente}" in bad.json()["detail"]
    assert "sin cerrar" in client.patch(ST, json={"expiring_message": "Hola {nombre"}, headers=h_admin).json()["detail"]
    assert client.patch(ST, json={"whatsapp_phone": "12"}, headers=h_admin).status_code == 422
    assert client.patch(ST, json={"tax_id": "abc"}, headers=h_admin).status_code == 422
    assert client.patch(ST, json={"overdue_message": "   "}, headers=h_admin).status_code == 422


def test_la_configuracion_es_por_gimnasio(client, db, h_admin):
    client.patch(ST, json={"name": "Lion Centro"}, headers=h_admin)
    hb = headers_for(make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=make_gym(db, "gym-b", name="Gym B")))
    assert client.get(ST, headers=hb).json()["name"] == "Gym B"


def test_el_comprobante_usa_los_datos_del_negocio(client, clock, h_admin, h_recep, create_member, plan):
    client.patch(ST, json={"whatsapp_phone": "88881234", "receipt_message": "Pura vida, campeón"}, headers=h_admin)
    m = create_member(phone="87776655")
    p = client.post("/api/v1/payments", json={"member_id": m["id"], "plan_id": plan["id"], "method": "efectivo"}, headers=h_recep).json()
    w = client.get(f"/api/v1/payments/{p['id']}/whatsapp", headers=h_recep).json()
    assert w["message"].endswith("Pura vida, campeón")
    rec = client.get(f"/api/v1/payments/{p['id']}/receipt", headers=h_recep).json()
    assert rec["gym"]["whatsapp_phone"] == "88881234"
    assert client.get(f"/api/v1/payments/{p['id']}/receipt.pdf", headers=h_recep).content.startswith(b"%PDF")


# ── IVA en planes ─────────────────────────────────────────────────────────────
def test_plan_con_tarifa_de_iva_y_pago_guarda_la_tarifa(client, clock, h_admin, h_recep, create_member):
    exento = client.post("/api/v1/plans", json={"name": "Clase de prueba", "duration_days": 1, "price": "1000", "tax_rate": "0"},
                         headers=h_admin).json()
    assert exento["tax_rate"] == "0.00"
    assert client.post("/api/v1/plans", json={"name": "Mal", "duration_days": 1, "price": "1", "tax_rate": "200"},
                       headers=h_admin).status_code == 422
    p = client.post("/api/v1/payments", json={"member_id": create_member()["id"], "plan_id": exento["id"], "method": "efectivo"},
                    headers=h_recep).json()
    assert (p["tax_rate"], p["subtotal"], p["tax_amount"]) == ("0.00", "1000.00", "0.00")
    client.patch(f"/api/v1/plans/{exento['id']}", json={"tax_rate": "13"}, headers=h_admin)
    again = client.get(f"/api/v1/payments/{p['id']}", headers=h_recep).json()
    assert again["tax_rate"] == "0.00"                          # el pago conserva la tarifa con que se cobró


# ── Inscripción con cobro ─────────────────────────────────────────────────────
def enroll(client, headers, plan, **payment):
    return client.post(EN, json={
        "member": {"identification": "114440555", "first_name": "Laura", "last_name": "Jiménez", "phone": "8888-1234"},
        "payment": {"plan_id": plan["id"], "method": "efectivo", **payment},
    }, headers=headers)


def test_inscribir_crea_socio_activo_con_membresia_y_comprobante(client, clock, h_recep, plan):
    r = enroll(client, h_recep, plan)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["member"]["status"] == "activo" and b["member"]["membership"]["plan_name"] == "Mensual"
    assert b["payment"]["receipt_code"] == "R-000001" and b["payment"]["member"]["id"] == b["member"]["id"]
    assert b["payment"]["period"] == {"start_date": "2026-10-10", "end_date": "2026-11-08"}


def test_inscripcion_es_todo_o_nada(client, db, clock, h_recep, plan):
    r = enroll(client, h_recep, plan, method="sinpe")                   # falta la referencia
    assert r.status_code == 422 and r.json()["code"] == "reference_required"
    assert db.scalar(text("SELECT count(*) FROM members")) == 0           # el socio NO quedó creado
    bad_plan = enroll(client, h_recep, {"id": "00000000-0000-0000-0000-000000000000"})
    assert bad_plan.status_code == 404 and db.scalar(text("SELECT count(*) FROM members")) == 0
    assert enroll(client, h_recep, plan).status_code == 201
    dup = enroll(client, h_recep, plan)
    assert dup.status_code == 409 and dup.json()["code"] == "member_exists"


@pytest.mark.cash_required
def test_inscribir_exige_caja_abierta(client, db, clock, h_recep, plan):
    r = enroll(client, h_recep, plan)
    assert r.status_code == 409 and r.json()["code"] == "cash_session_required"
    assert db.scalar(text("SELECT count(*) FROM members")) == 0
    s = open_cash(client, h_recep)
    ok = enroll(client, h_recep, plan).json()
    assert ok["payment"]["cash_session_id"] == s["id"]


def test_inscribir_valida_datos_del_socio_y_permisos(client, clock, h_recep, h_trainer, plan):
    r = client.post(EN, json={"member": {"identification": "1", "first_name": "", "last_name": "X"},
                              "payment": {"plan_id": plan["id"], "method": "efectivo"}}, headers=h_recep)
    assert r.status_code == 422
    assert enroll(client, h_trainer, plan).status_code == 403
