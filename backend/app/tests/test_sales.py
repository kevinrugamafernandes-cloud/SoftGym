"""Punto de venta: ventas con IVA, descuento de inventario, caja unificada, ticket y WhatsApp."""
from urllib.parse import unquote

import pytest
from sqlalchemy import text

from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user, open_cash

S = "/api/v1/sales"
PR = "/api/v1/products"


def sell(client, headers, lines, method="efectivo", **kw):
    items = [{"product_id": p["id"], "quantity": q} for p, q in lines]
    return client.post(S, json={"items": items, "method": method, **kw}, headers=headers)


def stock_of(client, headers, product):
    return client.get(f"{PR}/{product['id']}", headers=headers).json()["stock"]


@pytest.fixture
def agua(create_product):
    return create_product(name="Agua 600 ml", price="1000", initial_stock=10, category="Bebidas")


@pytest.fixture
def barra(create_product):
    return create_product(name="Barra de proteína", price="1500", tax_rate="0", initial_stock=5)


def test_sin_caja_abierta_no_se_vende(client, clock, h_recep, agua):
    r = sell(client, h_recep, [(agua, 1)])
    assert r.status_code == 409 and r.json()["code"] == "cash_session_required"
    assert stock_of(client, h_recep, agua) == 10


def test_venta_con_desglose_de_iva_y_descuento_de_stock(client, clock, h_recep, agua, barra):
    s = open_cash(client, h_recep)
    r = sell(client, h_recep, [(agua, 2), (barra, 1)], customer_name="Cliente de paso")
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["sale_code"] == "V-000001" and v["sale_date"] == "2026-10-10" and v["cash_session_id"] == s["id"]
    assert v["cashier_name"] == "Usuario receptionist" and v["customer"]["name"] == "Cliente de paso"
    a, b = v["items"]
    assert (a["product_name"], a["quantity"], a["unit_price"], a["line_total"]) == ("Agua 600 ml", 2, "1000.00", "2000.00")
    assert (a["line_subtotal"], a["line_tax"], a["tax_rate"]) == ("1769.91", "230.09", "13.00")
    assert (b["line_subtotal"], b["line_tax"]) == ("1500.00", "0.00")                    # exento
    assert (v["subtotal"], v["tax_total"], v["total"]) == ("3269.91", "230.09", "3500.00")
    assert v["taxes"] == [{"rate": "13.00", "base": "1769.91", "tax": "230.09"},
                          {"rate": "0.00", "base": "1500.00", "tax": "0.00"}]
    assert stock_of(client, h_recep, agua) == 8 and stock_of(client, h_recep, barra) == 4
    mv = client.get(f"{PR}/{agua['id']}/movements", headers=h_recep).json()["items"][0]
    assert (mv["kind"], mv["quantity"], mv["stock_after"], mv["sale_code"]) == ("venta", -2, 8, "V-000001")
    assert sell(client, h_recep, [(agua, 1)]).json()["sale_code"] == "V-000002"          # consecutivo


def test_lineas_repetidas_se_suman_y_el_precio_lo_pone_el_servidor(client, clock, h_recep, agua):
    open_cash(client, h_recep)
    r = client.post(S, json={"items": [
        {"product_id": agua["id"], "quantity": 1, "unit_price": "1"},          # precio del cliente: ignorado
        {"product_id": agua["id"], "quantity": 2},
    ], "method": "efectivo", "total": "3"}, headers=h_recep)
    v = r.json()
    assert len(v["items"]) == 1 and v["items"][0]["quantity"] == 3 and v["total"] == "3000.00"


def test_stock_insuficiente_no_deja_nada(client, db, clock, h_recep, agua, barra):
    open_cash(client, h_recep)
    r = sell(client, h_recep, [(agua, 2), (barra, 6)])
    assert r.status_code == 409 and r.json()["code"] == "insufficient_stock"
    assert "Barra de proteína (pidió 6, hay 5)" in r.json()["detail"]
    assert stock_of(client, h_recep, agua) == 10 and stock_of(client, h_recep, barra) == 5   # nada se descontó
    assert db.scalar(text("SELECT count(*) FROM sales")) == 0
    assert sell(client, h_recep, [(barra, 5)]).json()["sale_code"] == "V-000001"           # número no consumido
    assert stock_of(client, h_recep, barra) == 0
    again = sell(client, h_recep, [(barra, 1)])
    assert again.status_code == 409 and "hay 0" in again.json()["detail"]


def test_productos_inactivos_inexistentes_o_de_otro_gimnasio(client, db, clock, h_recep, h_admin, agua):
    open_cash(client, h_recep)
    client.patch(f"{PR}/{agua['id']}", json={"is_active": False}, headers=h_admin)
    r = sell(client, h_recep, [(agua, 1)])
    assert r.status_code == 422 and r.json()["code"] == "product_inactive"
    ghost = {"id": "00000000-0000-0000-0000-000000000000"}
    assert sell(client, h_recep, [(ghost, 1)]).status_code == 404

    hb = headers_for(make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=make_gym(db, "gym-b")))
    foreign = client.post(PR, json={"name": "Ajeno", "price": "1", "initial_stock": 5}, headers=hb).json()
    assert sell(client, h_recep, [(foreign, 1)]).status_code == 404


def test_validaciones_de_la_venta(client, clock, h_recep, agua):
    open_cash(client, h_recep)
    r = sell(client, h_recep, [(agua, 1)], method="sinpe")
    assert r.status_code == 422 and r.json()["code"] == "reference_required"
    assert sell(client, h_recep, [(agua, 1)], method="sinpe", reference="SP-99").status_code == 201
    assert client.post(S, json={"items": [], "method": "efectivo"}, headers=h_recep).status_code == 422
    assert sell(client, h_recep, [(agua, 0)]).status_code == 422
    bad = sell(client, h_recep, [(agua, 1)], customer_phone="123")
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_phone"


def test_el_comprobante_conserva_los_datos_aunque_cambie_el_producto(client, clock, h_recep, h_admin, agua):
    open_cash(client, h_recep)
    v = sell(client, h_recep, [(agua, 1)]).json()
    client.patch(f"{PR}/{agua['id']}", json={"name": "Agua renombrada", "price": "5000"}, headers=h_admin)
    again = client.get(f"{S}/{v['id']}", headers=h_recep).json()
    assert again["items"][0]["product_name"] == "Agua 600 ml" and again["total"] == "1000.00"


# ── Anulación ─────────────────────────────────────────────────────────────────
def test_anular_devuelve_el_stock_y_solo_el_administrador(client, clock, h_recep, h_admin, agua):
    open_cash(client, h_recep)
    v = sell(client, h_recep, [(agua, 3)]).json()
    assert client.post(f"{S}/{v['id']}/void", json={"reason": "Cliente devolvió"}, headers=h_recep).status_code == 403
    short = client.post(f"{S}/{v['id']}/void", json={"reason": "no"}, headers=h_admin)
    assert short.status_code == 422 and "motivo" in short.json()["detail"]
    r = client.post(f"{S}/{v['id']}/void", json={"reason": "Cliente devolvió sellado"}, headers=h_admin)
    assert r.status_code == 200 and r.json()["is_voided"] and r.json()["voided_by_name"] == "Usuario admin"
    assert stock_of(client, h_admin, agua) == 10
    mv = client.get(f"{PR}/{agua['id']}/movements", headers=h_admin).json()["items"][0]
    assert (mv["kind"], mv["quantity"], mv["stock_after"]) == ("anulacion_venta", 3, 10)
    again = client.post(f"{S}/{v['id']}/void", json={"reason": "Otra vez"}, headers=h_admin)
    assert again.status_code == 409 and again.json()["code"] == "already_voided"


# ── Caja unificada ────────────────────────────────────────────────────────────
def test_las_ventas_suman_al_cierre_del_dia_y_al_turno(client, clock, h_recep, h_admin, create_member, plan, agua):
    s = open_cash(client, h_recep, "5000")
    client.post("/api/v1/payments", json={"member_id": create_member()["id"], "plan_id": plan["id"], "method": "efectivo"}, headers=h_recep)
    sell(client, h_recep, [(agua, 2)])
    sell(client, h_recep, [(agua, 1)], method="tarjeta", reference="AUT-1")
    voided = sell(client, h_recep, [(agua, 1)]).json()
    client.post(f"{S}/{voided['id']}/void", json={"reason": "Error de digitación"}, headers=h_admin)

    day = client.get("/api/v1/payments/cash-summary", headers=h_recep).json()
    assert day["total"] == "28000.00" and day["count"] == 3
    assert day["payments_total"] == "25000.00" and day["sales_total"] == "3000.00" and day["sales_count"] == 2
    assert day["sales_tax_total"] == "345.13"
    assert {m["method"]: m["total"] for m in day["by_method"]} == {"efectivo": "27000.00", "tarjeta": "1000.00"}
    assert day["voided_count"] == 1 and day["voided_total"] == "1000.00"

    turn = client.get(f"/api/v1/cash-sessions/{s['id']}", headers=h_recep).json()["summary"]
    assert turn["expected_cash"] == "32000.00"                                  # 5 000 + 25 000 + 2 000

    lst = client.get(S, params={"cash_session_id": s["id"], "include_voided": False}, headers=h_recep).json()
    assert lst["total"] == 2 and lst["totals"]["active_total"] == "3000.00" and lst["totals"]["voided_count"] == 1
    assert client.get(S, params={"method": "tarjeta"}, headers=h_recep).json()["total"] == 1


# ── Ticket PDF y WhatsApp ─────────────────────────────────────────────────────
def test_ticket_pdf(client, clock, h_recep, h_admin, agua, barra):
    open_cash(client, h_recep)
    v = sell(client, h_recep, [(agua, 2), (barra, 1)]).json()
    r = client.get(f"{S}/{v['id']}/ticket.pdf", headers=h_recep)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "venta-V-000001.pdf" in r.headers["content-disposition"]
    client.post(f"{S}/{v['id']}/void", json={"reason": "Prueba de anulación"}, headers=h_admin)
    assert client.get(f"{S}/{v['id']}/ticket.pdf", headers=h_recep).content.startswith(b"%PDF")


def test_whatsapp_con_el_telefono_del_cliente_o_uno_indicado(client, clock, h_recep, agua):
    open_cash(client, h_recep)
    v = sell(client, h_recep, [(agua, 2)], customer_name="Laura", customer_phone="8888-1234").json()
    w = client.get(f"{S}/{v['id']}/whatsapp", headers=h_recep).json()
    assert w["phone"] == "50688881234" and w["url"].startswith("https://wa.me/50688881234?text=")
    msg = unquote(w["url"].split("text=")[1])
    assert msg == w["message"]
    assert "*Lion Fitness Center*" in msg and "V-000001" in msg and "Cliente: Laura" in msg
    assert "2 x Agua 600 ml — ₡2 000,00" in msg and "IVA (13 %): ₡230,09" in msg and "*Total: ₡2 000,00*" in msg

    other = client.get(f"{S}/{v['id']}/whatsapp", params={"phone": "+1 305 555 0100"}, headers=h_recep).json()
    assert other["phone"] == "13055550100"


def test_whatsapp_sin_telefono_pide_uno(client, clock, h_recep, agua):
    open_cash(client, h_recep)
    v = sell(client, h_recep, [(agua, 1)]).json()
    r = client.get(f"{S}/{v['id']}/whatsapp", headers=h_recep)
    assert r.status_code == 422 and r.json()["code"] == "phone_required"
    assert client.get(f"{S}/{v['id']}/whatsapp", params={"phone": "12"}, headers=h_recep).status_code == 422


def test_venta_a_un_socio_usa_su_telefono(client, clock, h_recep, create_member, agua):
    open_cash(client, h_recep)
    m = create_member(phone="8777-6655")
    v = sell(client, h_recep, [(agua, 1)], member_id=m["id"]).json()
    assert v["customer"] == {"member_id": m["id"], "name": "Ana Mora", "phone": "87776655"}
    assert client.get(f"{S}/{v['id']}/whatsapp", headers=h_recep).json()["phone"] == "50687776655"
    assert client.get(S, params={"member_id": m["id"]}, headers=h_recep).json()["total"] == 1


def test_whatsapp_del_comprobante_de_membresia(client, clock, h_recep, create_member, plan):
    m = create_member(phone="88881234")
    p = client.post("/api/v1/payments", json={"member_id": m["id"], "plan_id": plan["id"], "method": "efectivo"}, headers=h_recep).json()
    w = client.get(f"/api/v1/payments/{p['id']}/whatsapp", headers=h_recep).json()
    assert w["phone"] == "50688881234"
    assert "Comprobante de pago *R-000001*" in w["message"] and "Vigencia: 10/10/2026 al 08/11/2026" in w["message"]
    assert "*Total pagado: ₡25 000,00*" in w["message"]
    nophone = create_member()
    p2 = client.post("/api/v1/payments", json={"member_id": nophone["id"], "plan_id": plan["id"], "method": "efectivo"}, headers=h_recep).json()
    assert client.get(f"/api/v1/payments/{p2['id']}/whatsapp", headers=h_recep).json()["code"] == "phone_required"
