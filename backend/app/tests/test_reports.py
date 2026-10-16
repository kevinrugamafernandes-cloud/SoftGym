"""Libro de ventas con IVA por tarifa, cierre mensual (con bloqueo del periodo), exportaciones y dashboard."""
import csv
import io

import pytest

from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user, open_cash

R = "/api/v1/reports"
P = "/api/v1/payments"
S = "/api/v1/sales"


def pay(client, h, member, plan, **kw):
    r = client.post(P, json={"member_id": member["id"], "plan_id": plan["id"], "method": "efectivo", **kw}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def octubre(client, clock, h_admin, h_recep, create_member, create_product, plan):
    """Sept: 1 cobro. Oct (hoy 10/10): 2 cobros (1 anulado), 2 ventas (13 % y exento) y 1 SINPE."""
    s = open_cash(client, h_recep, "5000")
    ana = create_member(first_name="Ana")
    pay(client, h_recep, ana, plan, payment_date="2026-09-15")                         # septiembre
    luis = create_member(first_name="Luis")
    pay(client, h_recep, luis, plan, payment_date="2026-10-02")                        # 25 000 efectivo
    eva = create_member(first_name="Eva")
    bad = pay(client, h_recep, eva, plan, amount="20000", method="sinpe", reference="SP1")
    client.post(f"{P}/{bad['id']}/void", json={"reason": "Monto equivocado"}, headers=h_admin)
    pay(client, h_recep, eva, plan, method="sinpe", reference="SP2")                    # 25 000 SINPE
    agua = create_product(name="Agua", price="1000", initial_stock=10)
    barra = create_product(name="Barra", price="1500", tax_rate="0", initial_stock=10)
    client.post(S, json={"items": [{"product_id": agua["id"], "quantity": 2}, {"product_id": barra["id"], "quantity": 1}],
                         "method": "efectivo", "customer_name": "Cliente"}, headers=h_recep)
    return {"session": s}


def test_libro_de_ventas_unifica_membresias_y_tienda_con_iva_por_tarifa(client, h_admin, octubre):
    b = client.get(f"{R}/sales-book", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}, headers=h_admin).json()
    rows = b["rows"]
    assert [(r["doc_type"], r["document"], r["voided"]) for r in rows] == [
        ("membresia", "R-000002", False), ("membresia", "R-000003", True),
        ("membresia", "R-000004", False), ("venta", "V-000001", False),
    ]
    m = rows[0]
    assert m["taxes"] == [{"rate": "13.00", "base": "22123.89", "tax": "2876.11"}] and m["total"] == "25000.00"
    assert "Membresía Mensual (02/10/2026 al 31/10/2026)" == m["detail"]
    v = rows[3]
    assert v["taxes"] == [{"rate": "13.00", "base": "1769.91", "tax": "230.09"}, {"rate": "0.00", "base": "1500.00", "tax": "0.00"}]

    s = b["summary"]
    assert (s["count"], s["total"], s["subtotal"], s["tax_total"]) == (3, "53500.00", "47517.69", "5982.31")
    assert s["by_rate"] == [
        {"rate": "13.00", "base": "46017.69", "tax": "5982.31", "total": "52000.00"},
        {"rate": "0.00", "base": "1500.00", "tax": "0.00", "total": "1500.00"},
    ]
    assert {t["doc_type"]: (t["count"], t["total"]) for t in s["by_type"]} == {"membresia": (2, "50000.00"), "venta": (1, "3500.00")}
    assert {x["method"]: x["total"] for x in s["by_method"]} == {"efectivo": "28500.00", "sinpe": "25000.00"}
    assert (s["voided_count"], s["voided_total"]) == (1, "20000.00")
    assert [d["date"] for d in s["by_day"]] == ["2026-10-02", "2026-10-10"]
    assert s["cash_sessions"]["count"] == 1 and s["cash_sessions"]["open_count"] == 1


def test_validaciones_y_permisos_del_libro(client, h_admin, h_recep):
    assert client.get(f"{R}/sales-book", params={"date_from": "2026-10-31", "date_to": "2026-10-01"}, headers=h_admin).json()["code"] == "invalid_range"
    assert client.get(f"{R}/sales-book", params={"date_from": "2025-01-01", "date_to": "2026-10-01"}, headers=h_admin).json()["code"] == "range_too_long"
    assert client.get(f"{R}/sales-book", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}, headers=h_recep).status_code == 403
    vacio = client.get(f"{R}/sales-book", params={"date_from": "2026-01-01", "date_to": "2026-01-31"}, headers=h_admin).json()
    assert vacio["rows"] == [] and vacio["summary"]["by_rate"] == [{"rate": "13.00", "base": "0.00", "tax": "0.00", "total": "0.00"}]


def test_csv_para_excel_en_espanol(client, h_admin, octubre):
    r = client.get(f"{R}/sales-book.csv", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}, headers=h_admin)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="libro-ventas_2026-10-01_2026-10-31.csv"' in r.headers["content-disposition"]
    assert r.content.startswith("﻿".encode())
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    header = next(x for x in rows if x and x[0] == "Fecha")
    data = [x for x in rows if x and x[0][:2].isdigit()]
    total = rows[-1]
    col = header.index
    assert len(data) == 4
    anulado = next(x for x in data if x[col("Estado")] == "ANULADO")
    assert anulado[col("Total")] == "0,00" and anulado[col("Monto anulado")] == "20000,00"
    assert total[0] == "TOTAL" and total[col("Total")] == "53500,00" and total[col("IVA 13%")] == "5982,31"
    assert total[col("Exento")] == "1500,00"
    assert sum(float(x[col("Total")].replace(",", ".")) for x in data) == 53500.0     # sumar la columna da el total real


def test_resumen_mensual_y_cierre(client, clock, h_admin, h_recep, octubre):
    sep = client.get(f"{R}/monthly", params={"year": 2026, "month": 9}, headers=h_admin).json()
    assert sep["status"] == "abierto" and sep["summary"]["total"] == "25000.00" and sep["label"] == "septiembre 2026"
    assert sep["can_close"] is True and sep["close_blockers"] == []

    oct_ = client.get(f"{R}/monthly", params={"year": 2026, "month": 10}, headers=h_admin).json()
    assert oct_["status"] == "en_curso" and oct_["close_blockers"][0] == "El mes todavía no ha terminado"
    r = client.post(f"{R}/monthly-closes", json={"year": 2026, "month": 10}, headers=h_admin)
    assert r.status_code == 422 and r.json()["code"] == "period_not_closable"

    closed = client.post(f"{R}/monthly-closes", json={"year": 2026, "month": 9, "notes": "Entregado a contabilidad"}, headers=h_admin)
    assert closed.status_code == 201, closed.text
    c = closed.json()
    assert c["status"] == "cerrado" and c["closed_by_name"] == "Usuario admin" and c["summary"]["total"] == "25000.00"
    assert c["notes"] == "Entregado a contabilidad"
    again = client.post(f"{R}/monthly-closes", json={"year": 2026, "month": 9}, headers=h_admin)
    assert again.status_code == 409 and again.json()["code"] == "period_already_closed"
    lst = client.get(f"{R}/monthly-closes", headers=h_admin).json()
    assert [(x["label"], x["total"]) for x in lst] == [("septiembre 2026", "25000.00")]
    assert client.post(f"{R}/monthly-closes", json={"year": 2026, "month": 8}, headers=h_recep).status_code == 403

    # Ya en noviembre, octubre no se cierra mientras su caja siga abierta.
    clock.set_local(2026, 11, 2)
    nov = client.get(f"{R}/monthly", params={"year": 2026, "month": 10}, headers=h_admin).json()
    assert nov["status"] == "abierto" and nov["can_close"] is False
    assert nov["close_blockers"] == ["La caja de Usuario receptionist (abierta el 10/10/2026) sigue abierta"]
    client.post(f"/api/v1/cash-sessions/{octubre['session']['id']}/close", json={"counted_cash": "58500"}, headers=h_recep)   # 5 000 + 2 × 25 000 + 3 500
    assert client.post(f"{R}/monthly-closes", json={"year": 2026, "month": 10}, headers=h_admin).status_code == 201
    pdf = client.get(f"{R}/monthly.pdf", params={"year": 2026, "month": 10}, headers=h_admin)
    assert pdf.content.startswith(b"%PDF")


def test_un_mes_cerrado_queda_bloqueado(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    p = pay(client, h_recep, m, plan, payment_date="2026-09-20")
    assert client.post(f"{R}/monthly-closes", json={"year": 2026, "month": 9}, headers=h_admin).status_code == 201
    v = client.post(f"{P}/{p['id']}/void", json={"reason": "Intento tardío"}, headers=h_admin)
    assert v.status_code == 409 and v.json()["code"] == "period_closed" and "septiembre 2026" in v.json()["detail"]
    late = client.post(P, json={"member_id": create_member()["id"], "plan_id": plan["id"], "method": "efectivo",
                                "payment_date": "2026-09-30"}, headers=h_recep)
    assert late.status_code == 409 and late.json()["code"] == "period_closed"
    assert pay(client, h_recep, create_member(), plan)["payment_date"] == "2026-10-10"     # octubre sigue abierto
    snap = client.get(f"{R}/monthly", params={"year": 2026, "month": 9}, headers=h_admin).json()
    assert snap["summary"]["total"] == "25000.00"


def test_venta_de_mes_cerrado_no_se_anula(client, clock, h_admin, h_recep, create_product):
    open_cash(client, h_admin, "0")
    agua = create_product(price="1000", initial_stock=5)
    sale = client.post(S, json={"items": [{"product_id": agua["id"], "quantity": 1}], "method": "efectivo"}, headers=h_admin).json()
    client.post(f"/api/v1/cash-sessions/{client.get('/api/v1/cash-sessions/current', headers=h_admin).json()['session']['id']}/close",
                json={"counted_cash": "1000"}, headers=h_admin)
    clock.set_local(2026, 11, 3)
    assert client.post(f"{R}/monthly-closes", json={"year": 2026, "month": 10}, headers=h_admin).status_code == 201
    r = client.post(f"{S}/{sale['id']}/void", json={"reason": "Devolución tardía"}, headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "period_closed"


def test_pdf_del_cierre_mensual(client, h_admin, octubre):
    r = client.get(f"{R}/monthly.pdf", params={"year": 2026, "month": 10}, headers=h_admin)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert 'filename="cierre-2026-10.pdf"' in r.headers["content-disposition"] and r.content.startswith(b"%PDF")
    empty = client.get(f"{R}/monthly.pdf", params={"year": 2026, "month": 1}, headers=h_admin)
    assert empty.content.startswith(b"%PDF")


def test_reportes_aislados_por_gimnasio(client, db, h_admin, octubre):
    hb = headers_for(make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=make_gym(db, "gym-b")))
    b = client.get(f"{R}/sales-book", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}, headers=hb).json()
    assert b["rows"] == [] and b["summary"]["total"] == "0.00"


# ── Dashboard ─────────────────────────────────────────────────────────────────
def test_dashboard_resume_el_dia(client, clock, h_admin, h_recep, h_trainer, create_member, create_product, plan):
    s = open_cash(client, h_recep, "1000")
    pay(client, h_recep, create_member(), plan)                              # hoy: 25 000
    pay(client, h_recep, create_member(), plan, payment_date="2026-09-05")   # moroso (venció 4/oct)
    pay(client, h_recep, create_member(), plan, payment_date="2026-09-13")   # por vencer (12/oct)
    create_member()                                                          # inscrito sin cobro: inactivo
    p = create_product(price="1000", initial_stock=1, min_stock=2)           # stock bajo
    client.post(S, json={"items": [{"product_id": p["id"], "quantity": 1}], "method": "efectivo"}, headers=h_recep)
    d = client.get("/api/v1/dashboard", headers=h_recep).json()
    assert (d["today_total"], d["today_memberships"], d["today_store"]) == ("26000.00", "25000.00", "1000.00")
    assert (d["members_active"], d["members_overdue"], d["members_expiring"], d["members_inactive"]) == (1, 1, 1, 1)
    assert d["month_total"] == "26000.00" and d["low_stock_count"] == 1 and d["members_new_month"] == 4
    assert d["my_session_open"] is True and d["open_sessions"][0]["expected_cash"] == "77000.00"   # 1 000 + 3 × 25 000 + 1 000
    assert client.get("/api/v1/dashboard", headers=h_admin).json()["my_session_open"] is False
    assert client.get("/api/v1/dashboard", headers=h_trainer).status_code == 403
    assert s["id"]
