"""Ventas y aperturas SIMULTÁNEAS con transacciones reales (cada hilo su propia sesión y commit)."""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.models.cash_session import CashSession, CashSessionStatus
from app.models.gym import Gym
from app.models.payment import PaymentMethod
from app.models.product import InventoryMovement, Product
from app.models.user import User, UserRole
from app.schemas.cash_session import CashSessionOpen
from app.schemas.sale import SaleCreate, SaleLineIn
from app.services.cash_session_service import CashSessionService
from app.services.sale_service import InsufficientStockException, SaleService
from app.tests.conftest import FixedClock, _PASSWORD_HASH

CASHIERS = 4
STOCK = 6
BUYERS = 12


@pytest.fixture
def shop(test_engine):
    """Gimnasio propio con datos COMMITEADOS: 4 cajeras con caja abierta y un producto con 6 unidades."""
    slug = f"pos-{uuid.uuid4().hex[:8]}"
    clock = FixedClock()
    with Session(test_engine) as s:
        gym = Gym(name="Concurrencia POS", slug=slug)
        s.add(gym)
        s.flush()
        users = [User(gym_id=gym.id, full_name=f"Cajera {i}", email=f"{slug}-{i}@x.com", password_hash=_PASSWORD_HASH,
                      role=UserRole.RECEPTIONIST) for i in range(CASHIERS)]
        product = Product(gym_id=gym.id, name="Agua", price=Decimal("1000"), tax_rate=Decimal("13"), stock=STOCK, min_stock=0)
        s.add_all([*users, product])
        s.flush()
        for u in users:
            s.add(CashSession(gym_id=gym.id, cashier_id=u.id, status=CashSessionStatus.OPEN, business_date=clock.today("America/Costa_Rica"),
                              opened_at=clock.now(), opening_float=Decimal("0")))
        s.commit()
        ctx = {"gym": gym.id, "users": [u.id for u in users], "product": product.id}

    yield ctx

    with Session(test_engine) as s:
        g = {"g": ctx["gym"]}
        s.execute(text("DELETE FROM inventory_movements WHERE gym_id = :g"), g)
        s.execute(text("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE gym_id = :g)"), g)
        for table in ("sales", "products", "cash_sessions", "document_sequences", "users"):
            s.execute(text(f"DELETE FROM {table} WHERE gym_id = :g"), g)
        s.execute(text("DELETE FROM gyms WHERE id = :g"), g)
        s.commit()


def _buy(engine, ctx, user_id, barrier):
    with Session(engine) as s:
        user = s.get(User, user_id)
        svc = SaleService(s, ctx["gym"], FixedClock())
        barrier.wait(timeout=10)
        try:
            return svc.register(SaleCreate(items=[SaleLineIn(product_id=ctx["product"], quantity=1)], method=PaymentMethod.CASH), user)
        except InsufficientStockException:
            return None


def test_doce_compradores_seis_unidades_nunca_stock_negativo(test_engine, shop):
    barrier = threading.Barrier(BUYERS)
    buyers = [shop["users"][i % CASHIERS] for i in range(BUYERS)]
    with ThreadPoolExecutor(max_workers=BUYERS) as pool:
        results = list(pool.map(lambda uid: _buy(test_engine, shop, uid, barrier), buyers))

    sold = [r for r in results if r is not None]
    assert len(sold) == STOCK and results.count(None) == BUYERS - STOCK          # exactamente 6 ventas
    assert sorted(r.sale_number for r in sold) == list(range(1, STOCK + 1))     # consecutivos sin huecos
    with Session(test_engine) as s:
        assert s.get(Product, shop["product"]).stock == 0
        afters = sorted(s.scalars(select(InventoryMovement.stock_after).where(InventoryMovement.product_id == shop["product"])).all())
        assert afters == list(range(0, STOCK))                                    # 5,4,3,2,1,0: cada venta vio el stock real


def test_dos_aperturas_simultaneas_de_la_misma_cajera(test_engine, shop):
    uid = shop["users"][0]
    with Session(test_engine) as s:                                            # cerrar su caja para reabrir
        s.execute(text("UPDATE cash_sessions SET status='cerrada', closed_at=now(), counted_cash=0, expected_cash=0, difference=0 "
                       "WHERE cashier_id = :u"), {"u": uid})
        s.commit()
    barrier = threading.Barrier(2)

    def _open():
        with Session(test_engine) as s:
            svc = CashSessionService(s, shop["gym"], FixedClock())
            user = s.get(User, uid)
            barrier.wait(timeout=10)
            try:
                return svc.open(CashSessionOpen(opening_float=Decimal("1000")), user).id
            except ConflictException as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: _open(), range(2)))
    assert "cash_session_already_open" in outcomes                              # la otra apertura choca
    with Session(test_engine) as s:
        open_count = s.scalar(text("SELECT count(*) FROM cash_sessions WHERE cashier_id = :u AND status = 'abierta'"), {"u": uid})
    assert open_count == 1
