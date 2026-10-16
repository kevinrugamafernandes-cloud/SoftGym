"""Sesiones de caja: apertura con fondo, cobros ligados al turno y cierre con arqueo."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user, open_cash

C = "/api/v1/cash-sessions"
P = "/api/v1/payments"
S = "/api/v1/sales"


def pay(client, headers, member, plan, **kw):
    return client.post(P, json={"member_id": member["id"], "plan_id": plan["id"], "method": "efectivo", **kw}, headers=headers)


def close(client, headers, session, counted, notes=None):
    return client.post(f"{C}/{session['id']}/close", json={"counted_cash": counted, "notes": notes}, headers=headers)


# ── Apertura ──────────────────────────────────────────────────────────────────
def test_abrir_caja_con_fondo_inicial(client, clock, h_recep):
    assert client.get(f"{C}/current", headers=h_recep).json() == {"session": None}
    s = open_cash(client, h_recep, "15000.50", "Fondo en billetes de mil")
    assert s["status"] == "abierta" and s["opening_float"] == "15000.50"
    assert s["business_date"] == "2026-10-10" and s["cashier"]["full_name"] == "Usuario receptionist"
    assert s["summary"]["expected_cash"] == "15000.50" and s["currency"] == "CRC"
    assert client.get(f"{C}/current", headers=h_recep).json()["session"]["id"] == s["id"]


def test_no_se_abren_dos_cajas_para_el_mismo_cajero(client, clock, h_recep, h_admin):
    open_cash(client, h_recep)
    r = client.post(f"{C}/open", json={"opening_float": "0"}, headers=h_recep)
    assert r.status_code == 409 and r.json()["code"] == "cash_session_already_open"
    open_cash(client, h_admin)                                      # otro cajero sí puede tener la suya


def test_la_bd_impide_dos_cajas_abiertas_del_mismo_cajero(db, receptionist):
    """Última línea de defensa ante dos aperturas simultáneas: índice único parcial."""
    sql = text(
        "INSERT INTO cash_sessions (id, gym_id, cashier_id, status, business_date, opened_at, opening_float) "
        "VALUES (gen_random_uuid(), :g, :c, 'abierta', current_date, now(), 0)"
    )
    db.execute(sql, {"g": receptionist.gym_id, "c": receptionist.id})
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.execute(sql, {"g": receptionist.gym_id, "c": receptionist.id})


def test_validaciones_de_apertura_en_espanol(client, clock, h_recep, h_trainer, h_socio):
    r = client.post(f"{C}/open", json={"opening_float": "-1"}, headers=h_recep)
    assert r.status_code == 422 and "Fondo inicial" in r.json()["detail"]
    assert client.post(f"{C}/open", json={}, headers=h_recep).status_code == 422
    assert client.post(f"{C}/open", json={"opening_float": "0"}, headers=h_trainer).status_code == 403
    assert client.post(f"{C}/open", json={"opening_float": "0"}, headers=h_socio).status_code == 403


# ── Cobros ligados al turno ───────────────────────────────────────────────────
@pytest.mark.cash_required
def test_sin_caja_abierta_no_se_cobra(client, clock, h_recep, create_member, plan):
    m = create_member()
    r = pay(client, h_recep, m, plan)
    assert r.status_code == 409 and r.json()["code"] == "cash_session_required"
    assert "Abra caja" in r.json()["detail"]
    s = open_cash(client, h_recep)
    ok = pay(client, h_recep, m, plan)
    assert ok.status_code == 201 and ok.json()["cash_session_id"] == s["id"]


@pytest.mark.cash_required
def test_resumen_del_turno_y_efectivo_esperado(client, clock, h_recep, h_admin, create_member, plan, create_product):
    s = open_cash(client, h_recep, "10000")
    pay(client, h_recep, create_member(), plan)                                          # 25 000 efectivo
    pay(client, h_recep, create_member(), plan, method="sinpe", reference="SP-1")        # 25 000 SINPE
    prod = create_product(price="1500", initial_stock=5)
    assert client.post(S, json={"items": [{"product_id": prod["id"], "quantity": 2}], "method": "efectivo"},
                       headers=h_recep).status_code == 201                               # 3 000 efectivo
    assert pay(client, h_admin, create_member(), plan).status_code == 409   # otro usuario sin caja: no entra aquí

    got = client.get(f"{C}/{s['id']}", headers=h_recep).json()["summary"]
    assert got["payments_count"] == 2 and got["payments_total"] == "50000.00"
    assert got["sales_count"] == 1 and got["sales_total"] == "3000.00" and got["sales_tax_total"] == "345.13"
    assert got["total"] == "53000.00"
    assert got["cash_payments_total"] == "25000.00" and got["cash_sales_total"] == "3000.00"
    assert got["expected_cash"] == "38000.00"                                          # 10 000 + 25 000 + 3 000
    methods = {m["method"]: m for m in got["by_method"]}
    assert methods["efectivo"]["total"] == "28000.00" and methods["sinpe"]["payments_total"] == "25000.00"
    assert [m["method"] for m in got["by_method"]] == ["efectivo", "sinpe"]


@pytest.mark.cash_required
def test_lo_anulado_no_cuenta_en_el_esperado(client, clock, h_recep, h_admin, create_member, plan):
    s = open_cash(client, h_recep, "5000")
    p = pay(client, h_recep, create_member(), plan).json()
    client.post(f"{P}/{p['id']}/void", json={"reason": "Cobro equivocado"}, headers=h_admin)
    got = client.get(f"{C}/{s['id']}", headers=h_recep).json()["summary"]
    assert got["expected_cash"] == "5000.00" and got["voided_count"] == 1 and got["voided_total"] == "25000.00"


# ── Cierre y arqueo ───────────────────────────────────────────────────────────
@pytest.mark.cash_required
def test_cerrar_caja_cuadrada(client, clock, h_recep, create_member, plan):
    s = open_cash(client, h_recep, "10000")
    pay(client, h_recep, create_member(), plan)
    clock.advance(hours=8)
    r = close(client, h_recep, s, "35000")
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["status"] == "cerrada" and c["closed_at"] and c["closed_by_name"] == "Usuario receptionist"
    assert c["expected_cash"] == "35000.00" and c["counted_cash"] == "35000.00" and c["difference"] == "0.00"
    assert client.get(f"{C}/current", headers=h_recep).json() == {"session": None}
    after = pay(client, h_recep, create_member(), plan)                    # sin caja abierta ya no cobra
    assert after.status_code == 409 and after.json()["code"] == "cash_session_required"


@pytest.mark.cash_required
def test_faltante_o_sobrante_exige_observacion_y_se_guarda(client, clock, h_recep, create_member, plan):
    s = open_cash(client, h_recep, "10000")
    pay(client, h_recep, create_member(), plan)
    r = close(client, h_recep, s, "34500")
    assert r.status_code == 422 and r.json()["code"] == "closing_notes_required"
    assert client.get(f"{C}/current", headers=h_recep).json()["session"]["status"] == "abierta"   # no se cerró
    c = close(client, h_recep, s, "34500", "Se dio vuelto de más a un socio").json()
    assert c["difference"] == "-500.00" and c["closing_notes"] == "Se dio vuelto de más a un socio"

    s2 = open_cash(client, h_recep, "0")
    assert close(client, h_recep, s2, "200", "Moneda encontrada en gaveta").json()["difference"] == "200.00"


def test_no_se_cierra_dos_veces(client, clock, h_recep):
    s = open_cash(client, h_recep, "0")
    assert close(client, h_recep, s, "0").status_code == 200
    again = close(client, h_recep, s, "0")
    assert again.status_code == 409 and again.json()["code"] == "cash_session_closed"


def test_solo_el_cajero_o_un_administrador_cierra(client, db, clock, h_recep, h_admin):
    s = open_cash(client, h_recep, "1000")
    otra = headers_for(make_user(db, UserRole.RECEPTIONIST, "otra@lionfitness.com"))
    assert close(client, otra, s, "1000").status_code in (403, 404)
    c = close(client, h_admin, s, "1000").json()                           # el admin cierra un turno olvidado
    assert c["status"] == "cerrada" and c["closed_by_name"] == "Usuario admin" and c["cashier"]["full_name"] == "Usuario receptionist"


@pytest.mark.cash_required
def test_el_cierre_es_una_instantanea_que_no_cambia(client, clock, h_recep, h_admin, create_member, plan):
    s = open_cash(client, h_recep, "0")
    p = pay(client, h_recep, create_member(), plan).json()
    close(client, h_recep, s, "25000")
    client.post(f"{P}/{p['id']}/void", json={"reason": "Anulado al día siguiente"}, headers=h_admin)
    got = client.get(f"{C}/{s['id']}", headers=h_admin).json()
    assert got["expected_cash"] == "25000.00" and got["difference"] == "0.00"       # lo guardado no cambia
    assert got["summary"]["expected_cash"] == "0.00"                                 # el cálculo en vivo sí


# ── Historial y visibilidad ───────────────────────────────────────────────────
def test_historial_la_recepcionista_ve_solo_sus_turnos(client, db, clock, h_recep, h_admin):
    mine = open_cash(client, h_recep, "100")
    close(client, h_recep, mine, "100")
    admin_s = open_cash(client, h_admin, "0")
    r = client.get(C, headers=h_recep).json()
    assert r["total"] == 1 and r["items"][0]["id"] == mine["id"] and r["items"][0]["difference"] == "0.00"
    assert client.get(f"{C}/{admin_s['id']}", headers=h_recep).status_code == 404
    all_ = client.get(C, headers=h_admin).json()
    assert all_["total"] == 2
    assert client.get(C, params={"status": "abierta"}, headers=h_admin).json()["items"][0]["id"] == admin_s["id"]
    assert client.get(C, params={"date_from": "2026-10-11"}, headers=h_admin).json()["total"] == 0


def test_otro_gimnasio_no_ve_las_cajas(client, db, clock, h_recep):
    s = open_cash(client, h_recep)
    hb = headers_for(make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=make_gym(db, "gym-b")))
    assert client.get(f"{C}/{s['id']}", headers=hb).status_code == 404
    assert client.get(C, headers=hb).json()["total"] == 0
    assert close(client, hb, s, "10000").status_code == 404


def test_dia_de_negocio_segun_zona_del_gimnasio(client, clock, h_recep):
    clock.set_local(2026, 10, 10, 23)          # 11 p. m. en Costa Rica = 05:00 UTC del día 11
    assert open_cash(client, h_recep)["business_date"] == "2026-10-10"
