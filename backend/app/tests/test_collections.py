"""Morosos y por vencer con recordatorio por WhatsApp (wa.me)."""
from urllib.parse import unquote

from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user

C = "/api/v1/collections"
M = "/api/v1/members"


def pay(client, h, member, plan, **kw):
    r = client.post("/api/v1/payments", json={"member_id": member["id"], "plan_id": plan["id"], "method": "efectivo", **kw}, headers=h)
    assert r.status_code == 201, r.text


def test_lista_de_morosos_con_mensaje_y_enlace(client, clock, h_recep, h_admin, create_member, plan):
    tarde = create_member(first_name="laura maría", last_name="Jiménez", phone="8888-1234")
    pay(client, h_recep, tarde, plan, payment_date="2026-08-20")          # venció el 18/sep
    reciente = create_member(first_name="Pedro", phone="87776655")
    pay(client, h_recep, reciente, plan, payment_date="2026-09-05")       # venció el 04/oct
    sin_tel = create_member(first_name="Ana")
    pay(client, h_recep, sin_tel, plan, payment_date="2026-09-01")
    pronto = create_member(first_name="Carla", phone="86665544")
    pay(client, h_recep, pronto, plan, payment_date="2026-09-13")         # vence el 12/oct (2 días)
    al_dia = create_member(first_name="Diego")
    pay(client, h_recep, al_dia, plan)
    nunca = create_member(first_name="Nunca")                             # nunca pagó: no es moroso
    baja = create_member(first_name="Baja", phone="85554433")
    pay(client, h_recep, baja, plan, payment_date="2026-08-01")
    client.delete(f"{M}/{baja['id']}", headers=h_admin)

    r = client.get(C, headers=h_recep).json()
    assert r["overdue_count"] == 3 and r["expiring_count"] == 1 and r["total"] == 3
    names = [i["full_name"] for i in r["items"]]
    assert names[0].startswith("Pedro") and nunca["id"] not in [i["member_id"] for i in r["items"]]
    laura = next(i for i in r["items"] if i["member_id"] == tarde["id"])
    assert laura["days"] == 22 and laura["end_date"] == "2026-09-18" and laura["label"] == "Venció hace 22 días"
    assert laura["message"].startswith("Hola Laura, te saludamos de Lion Fitness Center.")
    assert "venció el 18/09/2026" in laura["message"]
    assert laura["whatsapp_url"].startswith("https://wa.me/50688881234?text=")
    assert unquote(laura["whatsapp_url"].split("text=")[1]) == laura["message"]
    ana = next(i for i in r["items"] if i["member_id"] == sin_tel["id"])
    assert ana["whatsapp_url"] is None

    p = client.get(C, params={"state": "por_vencer"}, headers=h_recep).json()
    assert [i["member_id"] for i in p["items"]] == [pronto["id"]]
    assert "vence el 12/10/2026 (en 2 días)" in p["items"][0]["message"]

    assert client.get(C, params={"search": "jimenez"}, headers=h_recep).json()["total"] == 1   # sin tildes


def test_plantilla_personalizada_y_renovacion_lo_saca_de_la_lista(client, clock, h_admin, h_recep, create_member, plan):
    client.patch("/api/v1/settings", json={"overdue_message": "{gimnasio}: {nombre}, tu {plan} venció {dias}. Tel {telefono}",
                                           "whatsapp_phone": "22223333"}, headers=h_admin)
    m = create_member(first_name="Laura", phone="88881234")
    pay(client, h_recep, m, plan, payment_date="2026-09-05")
    item = client.get(C, headers=h_recep).json()["items"][0]
    assert item["message"] == "Lion Fitness Center: Laura, tu Mensual venció hace 6 días. Tel 22223333"
    pay(client, h_recep, m, plan, confirm_duplicate=True)                    # renueva hoy
    assert client.get(C, headers=h_recep).json()["total"] == 0


def test_registrar_recordatorio_enviado(client, clock, h_recep, h_trainer, create_member, plan):
    m = create_member(phone="88881234")
    pay(client, h_recep, m, plan, payment_date="2026-09-01")
    r = client.post(f"{C}/{m['id']}/reminders", json={"kind": "vencida"}, headers=h_recep)
    assert r.status_code == 201 and r.json()["kind"] == "vencida"
    assert client.get(C, headers=h_recep).json()["items"][0]["last_reminder_at"]
    sin = create_member()
    assert client.post(f"{C}/{sin['id']}/reminders", json={"kind": "vencida"}, headers=h_recep).json()["code"] == "phone_required"
    assert client.get(C, headers=h_trainer).status_code == 403


def test_morosos_aislados_por_gimnasio(client, db, clock, h_recep, create_member, plan):
    m = create_member(phone="88881234")
    pay(client, h_recep, m, plan, payment_date="2026-09-01")
    hb = headers_for(make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=make_gym(db, "gym-b")))
    assert client.get(C, headers=hb).json()["total"] == 0
    assert client.post(f"{C}/{m['id']}/reminders", json={"kind": "vencida"}, headers=hb).status_code == 404
