"""Cobros: membresía, vigencia, comprobante, estado del socio y reglas de control."""
import pytest

from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user

P = "/api/v1/payments"
M = "/api/v1/members"
NO_EXISTE = "00000000-0000-0000-0000-000000000000"


def pay(client, headers, member, plan, **kw):
    body = {"member_id": member["id"], "plan_id": plan["id"], "method": "efectivo", **kw}
    return client.post(P, json=body, headers=headers)


def member_of(client, headers, member_id):
    return client.get(f"{M}/{member_id}", headers=headers).json()


# ── El cobro crea todo lo necesario ───────────────────────────────────────────
def test_primer_pago_crea_membresia_comprobante_y_estado(client, clock, h_recep, h_admin, create_member, plan):
    m = create_member()
    r = pay(client, h_recep, m, plan)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["receipt_code"] == "R-000001" and p["receipt_number"] == 1
    assert p["amount"] == "25000.00" and p["list_price"] == "25000.00" and p["discount"] == "0"
    assert p["period"] == {"start_date": "2026-10-10", "end_date": "2026-11-08"}   # 30 días: 10/oct → 8/nov (inclusive)
    assert p["payment_date"] == "2026-10-10" and p["method"] == "efectivo"
    assert p["member"]["full_name"] == "Ana Mora" and p["plan"]["name"] == "Mensual"
    assert p["registered_by_name"] == "Usuario receptionist" and p["is_voided"] is False

    got = member_of(client, h_admin, m["id"])
    assert got["status"] == "activo"
    assert got["membership"] == {
        "id": got["membership"]["id"], "plan_id": plan["id"], "plan_name": "Mensual",
        "start_date": "2026-10-10", "end_date": "2026-11-08", "days_remaining": 29, "days_overdue": 0,
        "state": "vigente", "label": "Vence en 29 días"}


def test_renovar_antes_de_vencer_no_pierde_dias(client, clock, h_recep, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan)                                         # 10/oct → 8/nov
    r = pay(client, h_recep, m, plan, confirm_duplicate=True)             # renueva el mismo día
    assert r.json()["period"] == {"start_date": "2026-11-09", "end_date": "2026-12-08"}   # empieza al día siguiente del vencimiento
    assert r.json()["receipt_code"] == "R-000002"


def test_renovar_despues_de_vencer_empieza_en_la_fecha_del_pago(client, clock, h_recep, h_admin, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan)                                         # vence el 8/nov
    clock.set_local(2026, 11, 20)                                          # 12 días de atraso (reloj simulado)
    # confirm_duplicate: el guardián de duplicados usa la hora REAL de la BD (aquí pasaron segundos).
    r = pay(client, h_recep, m, plan, confirm_duplicate=True)
    assert r.json()["period"] == {"start_date": "2026-11-20", "end_date": "2026-12-19"}
    assert member_of(client, h_admin, m["id"])["status"] == "activo"


def test_pagar_el_ultimo_dia_aun_cuenta_como_vigente_y_renueva_sin_hueco(client, clock, h_recep, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan)                                         # último día de acceso: 8/nov
    clock.set_local(2026, 11, 8)
    r = pay(client, h_recep, m, plan, confirm_duplicate=True)             # (ver nota sobre el reloj simulado arriba)
    assert r.json()["period"]["start_date"] == "2026-11-09"               # sin hueco ni solape


def test_pago_atrasado_registrado_hoy_deja_al_socio_moroso(client, clock, h_recep, h_admin, create_member, plan):
    """Pasar una ficha en papel: el pago es del 1/sep, ya cubrió hasta el 30/sep → hoy está vencido."""
    m = create_member()
    r = pay(client, h_recep, m, plan, payment_date="2026-09-01")
    assert r.status_code == 201 and r.json()["period"] == {"start_date": "2026-09-01", "end_date": "2026-09-30"}
    got = member_of(client, h_admin, m["id"])
    assert got["status"] == "moroso"
    assert got["membership"]["state"] == "vencida" and got["membership"]["days_overdue"] == 10
    assert got["membership"]["label"] == "Venció hace 10 días"
    hist = client.get(f"{M}/{m['id']}/memberships", headers=h_admin).json()
    assert hist[0]["status"] == "vencida"


def test_un_pago_por_vencer_marca_al_socio_por_vencer(client, clock, h_recep, h_admin, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan, payment_date="2026-09-15")              # vence el 14/oct: faltan 4 días
    got = member_of(client, h_admin, m["id"])
    assert got["status"] == "por_vencer" and got["membership"]["label"] == "Vence en 4 días"


# ── La fecha "hoy" es la del gimnasio, no la de UTC ───────────────────────────
def test_de_noche_en_costa_rica_hoy_sigue_siendo_hoy(client, clock, h_recep, create_member, plan):
    clock.set_local(2026, 10, 10, 20)               # 20:00 CR = 02:00 UTC del 11/oct
    m = create_member()
    r = pay(client, h_recep, m, plan)
    assert r.json()["payment_date"] == "2026-10-10"                        # NO el 11 (el día de UTC)
    assert r.json()["period"]["start_date"] == "2026-10-10"
    future = pay(client, h_recep, m, plan, payment_date="2026-10-11", confirm_duplicate=True)
    assert future.status_code == 422 and future.json()["code"] == "payment_in_future"


# ── Montos y descuentos ───────────────────────────────────────────────────────
def test_monto_distinto_se_registra_como_descuento(client, clock, h_recep, create_member, plan):
    r = pay(client, h_recep, create_member(), plan, amount="20000")
    p = r.json()
    assert p["amount"] == "20000.00" and p["list_price"] == "25000.00" and p["discount"] == "5000.00"


def test_monto_cero_cortesia_es_valido_y_negativo_no(client, clock, h_recep, create_member, plan):
    assert pay(client, h_recep, create_member(), plan, amount="0").status_code == 201
    r = pay(client, h_recep, create_member(), plan, amount="-1")
    assert r.status_code == 422
    assert {"field": "amount", "message": "Debe ser mayor o igual que 0"} in r.json()["errors"]


def test_referencia_obligatoria_para_sinpe_y_transferencia(client, clock, h_recep, create_member, plan):
    for method in ("sinpe", "transferencia"):
        r = pay(client, h_recep, create_member(), plan, method=method)
        assert r.status_code == 422 and r.json()["code"] == "reference_required"
        assert "referencia" in r.json()["detail"]
    ok = pay(client, h_recep, create_member(), plan, method="sinpe", reference="  SINPE-889900 ")
    assert ok.status_code == 201 and ok.json()["reference"] == "SINPE-889900"
    assert pay(client, h_recep, create_member(), plan, method="efectivo").status_code == 201
    assert pay(client, h_recep, create_member(), plan, method="tarjeta").status_code == 201


def test_metodo_invalido_se_rechaza_en_espanol(client, clock, h_recep, create_member, plan):
    r = pay(client, h_recep, create_member(), plan, method="bitcoin")
    assert r.status_code == 422 and "Valores válidos" in r.json()["errors"][0]["message"]


# ── Protección contra el doble clic ───────────────────────────────────────────
def test_pago_identico_inmediato_se_detiene_y_se_puede_confirmar(client, clock, h_recep, create_member, plan):
    m = create_member()
    assert pay(client, h_recep, m, plan).status_code == 201
    dup = pay(client, h_recep, m, plan)
    assert dup.status_code == 409 and dup.json()["code"] == "possible_duplicate"
    assert pay(client, h_recep, m, plan, amount="24000").status_code == 201          # otro monto: no es duplicado
    assert pay(client, h_recep, m, plan, confirm_duplicate=True).status_code == 201  # confirmado a propósito
    assert client.get(P, headers=h_recep).json()["total"] == 3                      # y el rechazado NO se guardó


def test_el_duplicado_rechazado_no_deja_membresia_ni_numero_de_comprobante(client, clock, h_recep, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan)
    pay(client, h_recep, m, plan)                                                    # rechazado
    nxt = pay(client, h_recep, m, plan, confirm_duplicate=True)
    assert nxt.json()["receipt_code"] == "R-000002"                                  # sin saltos


# ── Validaciones de entidades ─────────────────────────────────────────────────
def test_plan_inactivo_no_se_vende(client, clock, h_recep, h_admin, create_member, plan):
    client.patch(f"/api/v1/plans/{plan['id']}", json={"is_active": False}, headers=h_admin)
    r = pay(client, h_recep, create_member(), plan)
    assert r.status_code == 422 and r.json()["code"] == "plan_inactive"


def test_socio_o_plan_inexistente_o_dado_de_baja(client, clock, h_recep, h_admin, create_member, plan):
    m = create_member()
    assert pay(client, h_recep, {"id": NO_EXISTE}, plan).json()["code"] == "member_not_found"
    assert pay(client, h_recep, m, {"id": NO_EXISTE}).json()["code"] == "plan_not_found"
    client.delete(f"{M}/{m['id']}", headers=h_admin)
    assert pay(client, h_recep, m, plan).status_code == 404                           # de baja: no se le cobra


def test_pagar_reactiva_a_un_socio_inactivo_y_a_un_moroso(client, clock, h_recep, h_admin, create_member, plan):
    m = create_member()
    client.patch(f"{M}/{m['id']}", json={"status": "inactivo"}, headers=h_recep)
    pay(client, h_recep, m, plan)
    assert member_of(client, h_admin, m["id"])["status"] == "activo"


def test_el_cobro_es_atomico_si_algo_falla_no_queda_nada(client, db, clock, h_recep, h_admin, create_member, plan, monkeypatch):
    from sqlalchemy import text
    from app.repositories.payment_repository import PaymentRepository
    m = create_member()

    def boom(self):
        raise RuntimeError("falla simulada al asignar el comprobante")

    monkeypatch.setattr(PaymentRepository, "next_receipt_number", boom)
    r = pay(client, h_recep, m, plan)
    assert r.status_code == 500 and "falla simulada" not in r.text           # no se filtran detalles internos
    monkeypatch.undo()
    assert db.scalar(text("SELECT count(*) FROM memberships")) == 0           # la membresía NO quedó huérfana
    assert db.scalar(text("SELECT count(*) FROM payments")) == 0
    assert member_of(client, h_admin, m["id"])["membership"] is None
    assert pay(client, h_recep, m, plan).json()["receipt_code"] == "R-000001"  # y el número no se consumió


# ── Comprobantes consecutivos y por gimnasio ──────────────────────────────────
def test_comprobantes_consecutivos_y_contador_independiente_por_gimnasio(client, db, clock, h_recep, h_admin, create_member, plan):
    for _ in range(3):
        pay(client, h_recep, create_member(), plan)
    assert [p["receipt_code"] for p in client.get(P, headers=h_admin).json()["items"]] == ["R-000003", "R-000002", "R-000001"]

    gym_b = make_gym(db, "gym-b")
    admin_b = make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=gym_b)
    hb = headers_for(admin_b)
    plan_b = client.post("/api/v1/plans", json={"name": "Mensual", "duration_days": 30, "price": "30000"}, headers=hb).json()
    mb = client.post(M, json={"identification": "300000001", "first_name": "B", "last_name": "B"}, headers=hb).json()
    assert pay(client, hb, mb, plan_b).json()["receipt_code"] == "R-000001"       # su propio contador
    # y un socio/plan de otro gimnasio no se puede usar cruzado
    assert pay(client, h_recep, mb, plan).status_code == 404
    assert pay(client, h_recep, create_member(), plan_b).status_code == 404


# ── Permisos ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("fixture,status", [("h_admin", 201), ("h_recep", 201), ("h_trainer", 403), ("h_socio", 403)])
def test_quien_puede_cobrar(client, clock, request, create_member, plan, fixture, status):
    assert pay(client, request.getfixturevalue(fixture), create_member(), plan).status_code == status


def test_sin_token_no_se_cobra(raw_client):
    assert raw_client.post(P, json={}).status_code == 403
    assert raw_client.get(P).status_code == 403


def test_validacion_en_espanol(client, clock, h_recep):
    r = client.post(P, json={}, headers=h_recep)
    assert r.status_code == 422 and r.json()["detail"].startswith("Datos inválidos. ")
    assert {e["field"] for e in r.json()["errors"]} == {"member_id", "plan_id", "method"}
