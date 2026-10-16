"""El listado y la ficha de socios muestran la membresía con el tiempo restante."""
from sqlalchemy import event

M = "/api/v1/members"
P = "/api/v1/payments"


def pay(client, headers, member, plan, **kw):
    r = client.post(P, json={"member_id": member["id"], "plan_id": plan["id"], "method": "efectivo", **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_listado_muestra_dias_restantes_y_alertas(client, clock, h_admin, h_recep, create_member, plan):
    fresh, soon, late, never = (create_member(first_name=n) for n in ("Fresca", "Pronto", "Tarde", "Nunca"))
    pay(client, h_recep, fresh, plan)                                          # vence en 29 días
    pay(client, h_recep, soon, plan, payment_date="2026-09-15")                # vence el 14/oct → 4 días
    pay(client, h_recep, late, plan, payment_date="2026-08-20")                # venció el 18/sep → 22 días de atraso
    by = {i["first_name"]: i for i in client.get(f"{M}?size=100", headers=h_admin).json()["items"]}

    assert by["Fresca"]["membership"]["state"] == "vigente" and by["Fresca"]["membership"]["days_remaining"] == 29
    assert by["Pronto"]["membership"]["state"] == "por_vencer" and by["Pronto"]["membership"]["label"] == "Vence en 4 días"
    assert by["Tarde"]["membership"] == {**by["Tarde"]["membership"], "state": "vencida", "days_remaining": -22,
                                         "days_overdue": 22, "label": "Venció hace 22 días"}
    assert by["Nunca"]["membership"] is None
    assert [by[n]["status"] for n in ("Fresca", "Pronto", "Tarde", "Nunca")] == ["activo", "por_vencer", "moroso", "inactivo"]  # sin pago: inactivo


def test_el_tiempo_restante_se_calcula_en_vivo_sin_esperar_al_cron(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan)                                              # vence el 8/nov
    assert client.get(f"{M}/{m['id']}", headers=h_admin).json()["membership"]["state"] == "vigente"
    clock.set_local(2026, 11, 6)                                               # faltan 2 días; el campo `status` aún es el viejo
    got = client.get(f"{M}/{m['id']}", headers=h_admin).json()
    assert got["membership"]["state"] == "por_vencer" and got["membership"]["label"] == "Vence en 2 días"
    assert got["status"] == "activo"                                           # el motor diario lo actualizará; la alerta ya es exacta


def test_la_ficha_y_las_respuestas_de_edicion_tambien_traen_la_membresia(client, clock, h_admin, h_recep, create_member, plan):
    m = create_member()
    pay(client, h_recep, m, plan)
    assert client.get(f"{M}/{m['id']}", headers=h_admin).json()["membership"]["plan_name"] == "Mensual"
    assert client.patch(f"{M}/{m['id']}", json={"notes": "x"}, headers=h_admin).json()["membership"]["days_remaining"] == 29


def test_la_membresia_mostrada_es_la_ultima_no_cancelada(client, clock, h_admin, h_recep, create_member, plan, plan90):
    m = create_member()
    pay(client, h_recep, m, plan)                                              # hasta 8/nov
    second = pay(client, h_recep, m, plan90)                                   # trimestral a continuación: 9/nov → 6/feb
    assert client.get(f"{M}/{m['id']}", headers=h_admin).json()["membership"]["plan_name"] == "Trimestral"
    client.post(f"{P}/{second['id']}/void", json={"reason": "Plan equivocado"}, headers=h_admin)
    assert client.get(f"{M}/{m['id']}", headers=h_admin).json()["membership"]["plan_name"] == "Mensual"


def test_historial_de_membresias(client, clock, h_admin, h_recep, h_trainer, create_member, plan, plan90):
    m = create_member()
    pay(client, h_recep, m, plan)
    pay(client, h_recep, m, plan90)
    h = client.get(f"{M}/{m['id']}/memberships", headers=h_admin).json()
    assert [(x["plan_name"], x["start_date"], x["end_date"], x["status"]) for x in h] == [
        ("Trimestral", "2026-11-09", "2027-02-06", "activa"), ("Mensual", "2026-10-10", "2026-11-08", "activa")]
    assert client.get(f"{M}/{m['id']}/memberships", headers=h_trainer).status_code == 403
    assert client.get(f"{M}/00000000-0000-0000-0000-000000000000/memberships", headers=h_admin).status_code == 404


def test_listar_no_hace_una_consulta_por_socio(client, db, test_engine, clock, h_admin, create_member):
    """La membresía de toda la página se obtiene en consultas fijas (sin N+1)."""
    counter = {"n": 0}

    def count(conn, cursor, statement, *a):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["n"] += 1

    def run():
        counter["n"] = 0
        assert client.get(f"{M}?size=100", headers=h_admin).status_code == 200
        return counter["n"]

    event.listen(test_engine, "before_cursor_execute", count)
    try:
        for _ in range(3):
            create_member()
        few = run()
        for _ in range(12):
            create_member()
        many = run()
    finally:
        event.remove(test_engine, "before_cursor_execute", count)
    assert few == many, f"consultas con 3 socios: {few}, con 15 socios: {many} (hay N+1)"


def test_la_fecha_de_ingreso_por_defecto_es_la_del_gimnasio_no_la_del_servidor(client, clock, h_recep):
    """Registrar a las 21:00 en Costa Rica (= 03:00 UTC del día siguiente) debe quedar con la fecha de Costa Rica."""
    clock.set_local(2026, 10, 10, 21)
    r = client.post(M, json={"identification": "100000777", "first_name": "Noche", "last_name": "Tarde"}, headers=h_recep)
    assert r.status_code == 201 and r.json()["joined_at"] == "2026-10-10"
    explicit = client.post(M, json={"identification": "100000778", "first_name": "A", "last_name": "B", "joined_at": "2026-01-15"}, headers=h_recep)
    assert explicit.json()["joined_at"] == "2026-01-15"                      # una fecha explícita se respeta
