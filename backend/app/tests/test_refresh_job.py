"""Motor de morosidad: recalcula el estado de los socios según el vencimiento."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.enums import MemberStatus
from app.models.member import Member
from app.models.membership import Membership, MembershipStatus
from app.models.user import UserRole
from app.services.status_refresh_service import StatusRefreshService
from app.tests.conftest import default_gym, headers_for, make_gym, make_user

M = "/api/v1/members"


def add_membership(db, member, plan, end, *, status=MembershipStatus.ACTIVE, gym=None):
    db.add(Membership(
        gym_id=(gym or default_gym(db)).id, member_id=uuid.UUID(member["id"]), plan_id=uuid.UUID(plan["id"]),
        start_date=date.fromisoformat(end).replace(day=1), end_date=date.fromisoformat(end), status=status))
    if status != MembershipStatus.CANCELLED:
        # Un socio nuevo nace "inactivo" hasta pagar; aquí la membresía se inserta directo (sin cobro),
        # así que se marca activo como lo haría su primer pago.
        db.get(Member, uuid.UUID(member["id"])).status = MemberStatus.ACTIVE
    db.commit()


def status_of(db, member):
    db.expire_all()
    return db.get(Member, uuid.UUID(member["id"])).status.value


@pytest.fixture
def world(db, client, clock, create_member, plan, h_admin):
    """Hoy = 10/oct/2026. Los que tienen membresía quedan 'activo' (como tras su primer pago)."""
    w = {k: create_member(first_name=k) for k in "ABCDEFGH"}
    add_membership(db, w["A"], plan, "2026-10-20")                                     # vigente
    add_membership(db, w["B"], plan, "2026-10-13")                                     # por vencer (3 días)
    add_membership(db, w["C"], plan, "2026-10-10")                                     # vence HOY
    add_membership(db, w["D"], plan, "2026-10-09")                                     # moroso (1 día)
    add_membership(db, w["E"], plan, "2026-09-01")                                     # inactivo a mano
    client.patch(f"{M}/{w['E']['id']}", json={"status": "inactivo"}, headers=h_admin)
    add_membership(db, w["F"], plan, "2026-09-01")                                     # dado de baja
    client.delete(f"{M}/{w['F']['id']}", headers=h_admin)
    # G: nunca pagó (sin membresías)
    add_membership(db, w["H"], plan, "2026-09-01", status=MembershipStatus.CANCELLED)  # solo una cancelada
    return w


def test_transiciones_de_estado(db, world, clock):
    result = StatusRefreshService(db, clock).refresh_gym(default_gym(db))
    assert [status_of(db, world[k]) for k in "ABCD"] == ["activo", "por_vencer", "por_vencer", "moroso"]
    assert status_of(db, world["E"]) == "inactivo"        # el inactivo manual NO se toca
    assert status_of(db, world["G"]) == "inactivo"        # nunca pagó: sigue inactivo (sin membresía)
    assert status_of(db, world["H"]) == "inactivo"        # una membresía cancelada no cuenta
    assert db.get(Member, uuid.UUID(world["F"]["id"])).status.value == "inactivo"   # baja: su estado no cambia por el motor
    assert result.members_updated == 3                     # B, C y D


def test_marca_vencidas_las_membresias_activas_con_fecha_pasada(db, world, clock):
    result = StatusRefreshService(db, clock).refresh_gym(default_gym(db))
    ended = db.scalars(select(Membership).where(Membership.status == MembershipStatus.EXPIRED)).all()
    assert {m.end_date for m in ended} == {date(2026, 10, 9), date(2026, 9, 1)}     # D, E y F (E y F por igual fecha)
    assert result.memberships_expired == 3


def test_es_idempotente(db, world, clock):
    svc = StatusRefreshService(db, clock)
    svc.refresh_gym(default_gym(db))
    second = svc.refresh_gym(default_gym(db))
    assert (second.members_updated, second.memberships_expired) == (0, 0)


def test_al_pasar_los_dias_el_estado_avanza(db, world, clock):
    svc = StatusRefreshService(db, clock)
    svc.refresh_gym(default_gym(db))
    clock.set_local(2026, 10, 14)                          # B vencía el 13: ahora moroso. A (20) → por vencer (6 días: aún no)
    svc.refresh_gym(default_gym(db))
    assert status_of(db, world["B"]) == "moroso" and status_of(db, world["A"]) == "activo"
    clock.set_local(2026, 10, 15)                          # A: faltan 5 días → por vencer
    svc.refresh_gym(default_gym(db))
    assert status_of(db, world["A"]) == "por_vencer"


def test_dias_de_gracia_configurables(db, world, clock, monkeypatch):
    monkeypatch.setattr(settings, "MEMBERSHIP_GRACE_DAYS", 3)
    StatusRefreshService(db, clock).refresh_gym(default_gym(db))
    assert status_of(db, world["D"]) == "por_vencer"       # 1 día de atraso, dentro de la gracia
    clock.set_local(2026, 10, 13)                          # D: 4 días de atraso → moroso
    StatusRefreshService(db, clock).refresh_gym(default_gym(db))
    assert status_of(db, world["D"]) == "moroso"


def test_ventana_de_aviso_configurable(db, world, clock, monkeypatch):
    monkeypatch.setattr(settings, "MEMBERSHIP_EXPIRING_DAYS", 10)
    StatusRefreshService(db, clock).refresh_gym(default_gym(db))
    assert status_of(db, world["A"]) == "por_vencer"       # faltan 10 días


def test_cada_gimnasio_usa_su_propia_zona_horaria(db, client, clock, create_member, plan):
    """20:00 en Costa Rica = 11:00 del día siguiente en Tokio: el mismo vencimiento es distinto."""
    clock.set_local(2026, 10, 10, 20)
    tokyo = make_gym(db, "gym-tokio", "Gym Tokio", timezone="Asia/Tokyo")
    admin_t = make_user(db, UserRole.ADMIN, "admin-tokio@otro.com", gym=tokyo)
    ht = headers_for(admin_t)
    plan_t = client.post("/api/v1/plans", json={"name": "Mensual", "duration_days": 30, "price": "1"}, headers=ht).json()
    m_t = client.post(M, json={"identification": "300000001", "first_name": "T", "last_name": "T"}, headers=ht).json()
    m_cr = create_member(first_name="CR")
    for member, gym in ((m_t, tokyo), (m_cr, default_gym(db))):
        add_membership(db, member, plan_t if gym is tokyo else plan, "2026-10-10", gym=gym)   # vence el 10/oct en ambos

    results = StatusRefreshService(db, clock).refresh_all()
    assert {r.gym_id for r in results} >= {tokyo.id, default_gym(db).id}
    assert status_of(db, m_cr) == "por_vencer"             # en CR todavía es 10/oct → último día
    assert status_of(db, m_t) == "moroso"                  # en Tokio ya es 11/oct → vencido


def test_endpoint_solo_administradores_y_solo_su_gimnasio(db, client, world, clock, h_admin, h_recep):
    assert client.post("/api/v1/system/refresh-statuses", headers=h_recep).status_code == 403
    assert client.post("/api/v1/system/refresh-statuses").status_code == 403

    other = make_gym(db, "gym-b")
    admin_b = make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=other)
    r = client.post("/api/v1/system/refresh-statuses", headers=headers_for(admin_b))
    assert r.status_code == 200 and r.json() == {"memberships_expired": 0, "members_updated": 0}
    assert status_of(db, world["D"]) == "activo"           # el gimnasio B NO tocó los socios del A

    r = client.post("/api/v1/system/refresh-statuses", headers=h_admin)
    assert r.status_code == 200 and r.json()["members_updated"] == 3
    assert [status_of(db, world[k]) for k in "BCD"] == ["por_vencer", "por_vencer", "moroso"]
