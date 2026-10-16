"""Anulación de pagos, listado con filtros y cierre de caja."""
import pytest

from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user

P = "/api/v1/payments"
M = "/api/v1/members"


def pay(client, headers, member, plan, **kw):
    r = client.post(P, json={"member_id": member["id"], "plan_id": plan["id"], "method": "efectivo", **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def void(client, headers, payment, reason="Cobro equivocado"):
    return client.post(f"{P}/{payment['id']}/void", json={"reason": reason}, headers=headers)


# ── Anular ────────────────────────────────────────────────────────────────────
def test_anular_conserva_el_registro_y_cancela_la_membresia(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    p = pay(client, h_recep, m, plan)
    r = void(client, h_admin, p, "Se cobró al socio equivocado")
    assert r.status_code == 200
    v = r.json()
    assert v["is_voided"] is True and v["void_reason"] == "Se cobró al socio equivocado"
    assert v["voided_by_name"] == "Usuario admin" and v["voided_at"]
    assert v["receipt_code"] == p["receipt_code"]                             # el comprobante sigue existiendo

    assert client.get(f"{P}/{p['id']}", headers=h_admin).json()["is_voided"] is True   # NO se borró
    hist = client.get(f"{M}/{m['id']}/memberships", headers=h_admin).json()
    assert hist[0]["status"] == "cancelada"
    got = client.get(f"{M}/{m['id']}", headers=h_admin).json()
    assert got["membership"] is None and got["status"] == "inactivo"          # sin membresía: no queda activo


def test_anular_exige_motivo_y_solo_el_administrador(client, clock, h_admin, h_recep, h_trainer, create_member, plan):
    p = pay(client, h_recep, create_member(), plan)
    short = client.post(f"{P}/{p['id']}/void", json={"reason": "no"}, headers=h_admin)
    assert short.status_code == 422 and "Indique el motivo" in short.json()["detail"]
    assert client.post(f"{P}/{p['id']}/void", json={}, headers=h_admin).status_code == 422
    assert void(client, h_recep, p).status_code == 403                         # la recepcionista no anula
    assert void(client, h_trainer, p).status_code == 403
    assert client.get(f"{P}/{p['id']}", headers=h_admin).json()["is_voided"] is False   # sigue intacto


def test_solo_se_anula_el_ultimo_pago_del_socio(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    first = pay(client, h_recep, m, plan)
    second = pay(client, h_recep, m, plan, confirm_duplicate=True)             # 9/nov → 8/dic
    r = void(client, h_admin, first)
    assert r.status_code == 409 and r.json()["code"] == "void_latest_first"
    assert void(client, h_admin, second).status_code == 200                    # primero el más reciente…
    assert void(client, h_admin, first).status_code == 200                     # …y luego el anterior


def test_no_se_anula_dos_veces(client, clock, h_admin, h_recep, create_member, plan):
    p = pay(client, h_recep, create_member(), plan)
    assert void(client, h_admin, p).status_code == 200
    again = void(client, h_admin, p)
    assert again.status_code == 409 and again.json()["code"] == "already_voided"


def test_al_anular_el_ultimo_el_socio_vuelve_al_estado_de_su_pago_anterior(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan, payment_date="2026-09-01")                   # venció el 30/sep → moroso
    clock.set_local(2026, 10, 10)
    renewal = pay(client, h_recep, m, plan, confirm_duplicate=True)            # activo hasta el 8/nov (guardián usa hora real)
    assert client.get(f"{M}/{m['id']}", headers=h_admin).json()["status"] == "activo"
    void(client, h_admin, renewal)
    got = client.get(f"{M}/{m['id']}", headers=h_admin).json()
    assert got["status"] == "moroso" and got["membership"]["end_date"] == "2026-09-30"


def test_tras_anular_se_puede_cobrar_de_nuevo_sin_huecos(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    wrong = pay(client, h_recep, m, plan, amount="20000")
    void(client, h_admin, wrong, "Monto incorrecto")
    right = pay(client, h_recep, m, plan, amount="25000")
    assert right["period"]["start_date"] == "2026-10-10"                       # la membresía cancelada no cuenta
    assert right["receipt_code"] == "R-000002"                                 # el número anulado NO se reutiliza


def test_se_puede_anular_el_pago_de_un_socio_dado_de_baja(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    p = pay(client, h_recep, m, plan)
    client.delete(f"{M}/{m['id']}", headers=h_admin)
    assert void(client, h_admin, p).status_code == 200


def test_pago_de_otro_gimnasio_no_se_ve_ni_se_anula(client, db, clock, h_admin, h_recep, create_member, plan):
    p = pay(client, h_recep, create_member(), plan)
    admin_b = make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=make_gym(db, "gym-b"))
    hb = headers_for(admin_b)
    assert client.get(f"{P}/{p['id']}", headers=hb).status_code == 404
    assert client.get(f"{P}/{p['id']}/receipt", headers=hb).status_code == 404
    assert client.get(f"{P}/{p['id']}/receipt.pdf", headers=hb).status_code == 404
    assert void(client, hb, p).status_code == 404
    assert client.get(P, headers=hb).json()["total"] == 0


# ── Cierre de caja ────────────────────────────────────────────────────────────
def test_cierre_de_caja_por_metodo_excluye_anulados(client, clock, h_admin, h_recep, create_member, plan, plan90):
    pay(client, h_recep, create_member(), plan)                                              # 25 000 efectivo
    pay(client, h_recep, create_member(), plan, amount="20000", method="tarjeta")            # 20 000 tarjeta
    pay(client, h_recep, create_member(), plan90, method="sinpe", reference="S-1")           # 65 000 sinpe
    bad = pay(client, h_recep, create_member(), plan, amount="5000")                          # se anulará
    void(client, h_admin, bad)

    r = client.get(f"{P}/cash-summary", headers=h_recep)
    assert r.status_code == 200
    s = r.json()
    assert s["date"] == "2026-10-10" and s["currency"] == "CRC"
    assert s["count"] == 3 and s["total"] == "110000.00"                      # los anulados NO suman
    assert {x["method"]: (x["count"], x["total"]) for x in s["by_method"]} == {
        "efectivo": (1, "25000.00"), "tarjeta": (1, "20000.00"), "sinpe": (1, "65000.00")}
    assert s["voided_count"] == 1 and s["voided_total"] == "5000.00"


def test_cierre_de_caja_de_otro_dia_y_dia_vacio(client, clock, h_recep, create_member, plan):
    pay(client, h_recep, create_member(), plan, payment_date="2026-10-08")
    assert client.get(f"{P}/cash-summary?date=2026-10-08", headers=h_recep).json()["total"] == "25000.00"
    empty = client.get(f"{P}/cash-summary?date=2026-10-09", headers=h_recep).json()
    assert empty["count"] == 0 and empty["total"] in ("0", "0.00")
    assert empty["by_method"] == []
    assert client.get(f"{P}/cash-summary?date=2026-10-10", headers=h_recep).json()["count"] == 0   # hoy: nada


def test_cierre_de_caja_usa_el_dia_del_gimnasio_no_el_de_utc(client, clock, h_recep, create_member, plan):
    clock.set_local(2026, 10, 10, 21)                                           # 21:00 CR = 03:00 UTC del 11/oct
    pay(client, h_recep, create_member(), plan)
    s = client.get(f"{P}/cash-summary", headers=h_recep).json()
    assert s["date"] == "2026-10-10" and s["count"] == 1                        # "hoy" por defecto = 10, no 11


@pytest.mark.parametrize("fixture,status", [("h_admin", 200), ("h_recep", 200), ("h_trainer", 403), ("h_socio", 403)])
def test_permisos_de_caja_y_listado(client, clock, request, fixture, status):
    h = request.getfixturevalue(fixture)
    assert client.get(f"{P}/cash-summary", headers=h).status_code == status
    assert client.get(P, headers=h).status_code == status


# ── Listado con filtros y totales ─────────────────────────────────────────────
def test_listado_filtros_y_totales_de_todo_el_filtro(client, clock, h_admin, h_recep, create_member, plan, plan90):
    a, b = create_member(first_name="Ana"), create_member(first_name="Beto")
    pay(client, h_recep, a, plan, payment_date="2026-09-05")
    pay(client, h_recep, a, plan90, payment_date="2026-10-02", method="sinpe", reference="X1")
    pay(client, h_recep, b, plan, payment_date="2026-10-09", method="tarjeta")
    gone = pay(client, h_recep, b, plan, payment_date="2026-10-09", amount="1000", method="tarjeta")
    void(client, h_admin, gone)

    everything = client.get(P, headers=h_admin).json()
    assert everything["total"] == 4 and everything["totals"] == {
        "active_count": 3, "active_total": "115000.00", "voided_count": 1, "voided_total": "1000.00"}
    assert client.get(f"{P}?include_voided=false", headers=h_admin).json()["total"] == 3
    assert client.get(f"{P}?method=tarjeta", headers=h_admin).json()["totals"]["active_total"] == "25000.00"
    assert client.get(f"{P}?member_id={a['id']}", headers=h_admin).json()["total"] == 2
    oct_only = client.get(f"{P}?date_from=2026-10-01&date_to=2026-10-31", headers=h_admin).json()
    assert oct_only["total"] == 3 and oct_only["totals"]["active_total"] == "90000.00"

    page1 = client.get(f"{P}?size=2&page=1", headers=h_admin).json()
    assert len(page1["items"]) == 2 and page1["pages"] == 2 and page1["totals"]["active_total"] == "115000.00"  # totales de TODO, no de la página
    assert [i["is_voided"] for i in everything["items"]].count(True) == 1


def test_el_listado_muestra_los_mas_recientes_primero(client, clock, h_admin, h_recep, create_member, plan):
    for day in ("2026-10-01", "2026-10-09", "2026-10-05"):
        pay(client, h_recep, create_member(), plan, payment_date=day)
    assert [p["payment_date"] for p in client.get(P, headers=h_admin).json()["items"]] == ["2026-10-09", "2026-10-05", "2026-10-01"]


def test_filtros_invalidos_en_espanol(client, clock, h_admin):
    r = client.get(f"{P}?date_from=ayer&size=500", headers=h_admin)
    assert r.status_code == 422
    msgs = {e["field"]: e["message"] for e in r.json()["errors"]}
    assert msgs["date_from"].startswith("Fecha inválida") and msgs["size"] == "Debe ser menor o igual que 100"
