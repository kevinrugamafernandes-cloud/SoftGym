"""Cobros SIMULTÁNEOS con transacciones reales (cada hilo su propia sesión y commit)."""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.gym import Gym
from app.models.member import Member
from app.models.membership import Membership
from app.models.payment import PaymentMethod
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.schemas.payment import PaymentCreate
from app.services.payment_service import PaymentService
from app.tests.conftest import FixedClock, _PASSWORD_HASH


@pytest.fixture
def committed_gym(test_engine):
    """Gimnasio propio con datos COMMITEADOS (no usa la sesión con rollback): el gym_id lo aísla del resto."""
    slug = f"conc-{uuid.uuid4().hex[:8]}"
    with Session(test_engine) as s:
        gym = Gym(name="Concurrencia", slug=slug)
        s.add(gym)
        s.flush()
        user = User(gym_id=gym.id, full_name="Cajera", email=f"{slug}@x.com", password_hash=_PASSWORD_HASH, role=UserRole.RECEPTIONIST)
        plan = Plan(gym_id=gym.id, name="Mensual", duration_days=30, price=Decimal("25000"))
        members = [Member(gym_id=gym.id, identification=f"9{i:08d}", first_name=f"M{i}", last_name="Test") for i in range(8)]
        s.add_all([user, plan, *members])
        s.commit()
        ctx = {"gym": gym.id, "user": user.id, "plan": plan.id, "members": [m.id for m in members]}

    yield ctx

    # Estos datos SÍ se commitearon: se borran para no contaminar a otras pruebas (que cuentan filas/gimnasios).
    # Orden inverso a las claves foráneas (los pagos son RESTRICT a propósito).
    with Session(test_engine) as s:
        for table in ("payments", "memberships", "body_measurements", "members", "plans", "users", "receipt_sequences"):
            s.execute(text(f"DELETE FROM {table} WHERE gym_id = :g"), {"g": ctx["gym"]})
        s.execute(text("DELETE FROM gyms WHERE id = :g"), {"g": ctx["gym"]})
        s.commit()


def _register(engine, ctx, member_id, *, confirm=False, barrier=None):
    with Session(engine) as s:
        user = s.get(User, ctx["user"])
        svc = PaymentService(s, ctx["gym"], FixedClock())
        if barrier:
            barrier.wait(timeout=10)
        return svc.register(
            PaymentCreate(member_id=member_id, plan_id=ctx["plan"], method=PaymentMethod.CASH, confirm_duplicate=confirm), user)


def test_ocho_cobros_simultaneos_reciben_comprobantes_unicos_y_consecutivos(test_engine, committed_gym):
    ctx = committed_gym
    barrier = threading.Barrier(len(ctx["members"]))
    with ThreadPoolExecutor(max_workers=len(ctx["members"])) as pool:
        results = list(pool.map(lambda mid: _register(test_engine, ctx, mid, barrier=barrier), ctx["members"]))
    numbers = sorted(r.receipt_number for r in results)
    assert numbers == list(range(1, 9)), numbers            # únicos, sin repetir y sin saltos


def test_dos_cobros_simultaneos_al_mismo_socio_no_solapan_sus_periodos(test_engine, committed_gym):
    ctx = committed_gym
    mid = ctx["members"][0]
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_register, test_engine, ctx, mid, confirm=True, barrier=barrier) for _ in range(2)]
        [f.result() for f in futures]
    with Session(test_engine) as s:
        periods = sorted(
            (m.start_date, m.end_date)
            for m in s.scalars(select(Membership).where(Membership.member_id == mid)).all())
    assert len(periods) == 2
    first, second = periods
    assert second[0] == first[1] + timedelta(days=1), periods     # el segundo empieza justo después del primero
    assert first[1] - first[0] == timedelta(days=29) and second[1] - second[0] == timedelta(days=29)
