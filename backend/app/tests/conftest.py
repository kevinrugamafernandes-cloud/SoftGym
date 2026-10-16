"""
Fixtures compartidas de la suite.

Las pruebas de API usan una base PostgreSQL REAL (las restricciones, los ENUM y la
extensión unaccent se comportan distinto en SQLite). Reglas de seguridad:

  * La BD de pruebas se toma de TEST_DATABASE_URL o, si no existe, se deriva de
    DATABASE_URL como "<nombre>_test" SOLO cuando el servidor es local/Docker
    (host db, localhost o 127.0.0.1). Con Supabase o cualquier host remoto, las
    pruebas de BD se OMITEN salvo que se defina TEST_DATABASE_URL explícitamente.
  * El nombre de la BD DEBE terminar en "_test"; de lo contrario la suite aborta.
  * Se aplican las migraciones reales (alembic upgrade head) sobre un esquema limpio.
  * Cada test corre dentro de una transacción que se revierte al terminar.

Las pruebas que no necesitan BD (validaciones, traducción, cliente de cédulas)
corren siempre, incluso sin PostgreSQL.
"""
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterator, Optional
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.clock import Clock, get_clock
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.gym import Gym
from app.models.user import User, UserRole

BACKEND_DIR = Path(__file__).resolve().parents[2]
PASSWORD = "Secreta123!"
_PASSWORD_HASH = hash_password(PASSWORD)  # bcrypt es lento: se calcula una sola vez


def _resolve_test_url() -> Optional[URL]:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return make_url(explicit)
    base = make_url(settings.DATABASE_URL)
    if base.host in {"db", "localhost", "127.0.0.1"} and base.database:
        return base.set(database=f"{base.database}_test")
    return None


@pytest.fixture(scope="session")
def test_engine() -> Iterator:
    url = _resolve_test_url()
    if url is None:
        pytest.skip(
            "Sin BD de pruebas: defina TEST_DATABASE_URL (el nombre debe terminar en _test)."
        )
    if not (url.database or "").endswith("_test"):
        pytest.exit(
            f"ABORTADO: la BD de pruebas '{url.database}' no termina en '_test'. "
            "Las pruebas borran el esquema; no se ejecutan contra una BD real.",
            returncode=2,
        )

    try:  # crear la BD de pruebas si no existe
        admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
        admin_engine.dispose()
    except OperationalError as exc:
        pytest.skip(f"No hay PostgreSQL disponible para las pruebas de BD: {exc.orig}")

    engine = create_engine(url)
    with engine.begin() as conn:  # esquema limpio
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    os.environ["ALEMBIC_DATABASE_URL"] = url.render_as_string(hide_password=False)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    remove_seeded_plans(engine)

    yield engine

    engine.dispose()
    os.environ.pop("ALEMBIC_DATABASE_URL", None)


def remove_seeded_plans(engine) -> None:
    """
    La migración 0007 siembra los planes oficiales (Pase de Día, Quincena, Mensualidad). Las pruebas
    parten de un catálogo vacío para no depender de ellos; test_migrations verifica la semilla.
    """
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM plans WHERE id NOT IN (SELECT plan_id FROM memberships)"))


@pytest.fixture
def db(test_engine) -> Iterator[Session]:
    """Sesión dentro de una transacción externa que se revierte: aislamiento total."""
    connection = test_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def raw_client() -> Iterator[TestClient]:
    """Cliente sin BD: para rutas que fallan antes de tocarla (auth, 404, etc.)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Caja obligatoria para cobrar ──────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _cash_session_policy(request) -> Iterator[None]:
    """
    En producción cobrar exige caja abierta (CASH_SESSION_REQUIRED=True). Las pruebas de cobros
    anteriores a las sesiones de caja no la abren: corren con la regla desactivada. Las pruebas que
    validan la regla se marcan con @pytest.mark.cash_required.
    """
    # Sin monkeypatch a propósito: varias pruebas llaman monkeypatch.undo() y revertirían esta regla.
    previous = settings.CASH_SESSION_REQUIRED
    settings.CASH_SESSION_REQUIRED = bool(request.node.get_closest_marker("cash_required"))
    yield
    settings.CASH_SESSION_REQUIRED = previous


# ── Usuarios y cabeceras ──────────────────────────────────────────────────────
def default_gym(db: Session) -> Gym:
    """Gimnasio que crea la migración 0005 (Lion Fitness Center)."""
    return db.scalars(select(Gym).where(Gym.slug == "lion-fitness-center")).one()


def make_gym(db: Session, slug: str, name: str = "Otro Gimnasio", timezone: str = "America/Costa_Rica") -> Gym:
    gym = Gym(name=name, slug=slug, timezone=timezone)
    db.add(gym)
    db.commit()
    db.refresh(gym)
    return gym


def make_user(
    db: Session, role: UserRole, email: Optional[str] = None, *, active: bool = True, gym: Optional[Gym] = None
) -> User:
    user = User(
        gym_id=(gym or default_gym(db)).id,
        full_name=f"Usuario {role.value}",
        email=email or f"{role.value}@lionfitness.com",
        password_hash=_PASSWORD_HASH,
        role=role,
        is_active=active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def headers_for(user: User) -> Dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


@pytest.fixture
def admin(db) -> User:
    return make_user(db, UserRole.ADMIN)


@pytest.fixture
def receptionist(db) -> User:
    return make_user(db, UserRole.RECEPTIONIST)


@pytest.fixture
def trainer(db) -> User:
    return make_user(db, UserRole.TRAINER)


@pytest.fixture
def socio_user(db) -> User:
    return make_user(db, UserRole.MEMBER)


@pytest.fixture
def h_admin(admin) -> Dict[str, str]:
    return headers_for(admin)


@pytest.fixture
def h_recep(receptionist) -> Dict[str, str]:
    return headers_for(receptionist)


@pytest.fixture
def h_trainer(trainer) -> Dict[str, str]:
    return headers_for(trainer)


@pytest.fixture
def h_socio(socio_user) -> Dict[str, str]:
    return headers_for(socio_user)


# ── Fábricas de datos vía API ─────────────────────────────────────────────────
@pytest.fixture
def create_member(client, h_admin) -> Callable[..., dict]:
    counter = {"n": 0}

    def _create(**overrides) -> dict:
        counter["n"] += 1
        payload = {
            "identification": f"1{counter['n']:08d}",
            "first_name": "Ana",
            "last_name": "Mora",
            **overrides,
        }
        r = client.post("/api/v1/members", json=payload, headers=h_admin)
        assert r.status_code == 201, r.text
        return r.json()

    return _create


# ── Reloj controlable ─────────────────────────────────────────────────────────
class FixedClock(Clock):
    """Reloj de pruebas. Por defecto: sábado 10/10/2026, 12:00 hora de Costa Rica (UTC-6)."""

    def __init__(self) -> None:
        self.set_local(2026, 10, 10, 12)

    def now(self) -> datetime:
        return self._now

    def set_local(self, year: int, month: int, day: int, hour: int = 12, tz: str = "America/Costa_Rica") -> None:
        self._now = datetime(year, month, day, hour, tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)

    def advance(self, **kwargs) -> None:
        self._now += timedelta(**kwargs)


@pytest.fixture
def clock() -> Iterator[FixedClock]:
    c = FixedClock()
    app.dependency_overrides[get_clock] = lambda: c
    yield c
    app.dependency_overrides.pop(get_clock, None)


@pytest.fixture
def plan(client, h_admin) -> dict:
    """Plan mensual: 30 días, ₡25 000."""
    r = client.post("/api/v1/plans", json={"name": "Mensual", "duration_days": 30, "price": "25000"}, headers=h_admin)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def plan90(client, h_admin) -> dict:
    r = client.post("/api/v1/plans", json={"name": "Trimestral", "duration_days": 90, "price": "65000"}, headers=h_admin)
    assert r.status_code == 201, r.text
    return r.json()


# ── Caja y punto de venta ─────────────────────────────────────────────────────
def open_cash(client, headers, opening_float: str = "10000", notes: Optional[str] = None) -> dict:
    """Abre la caja del usuario de `headers` y devuelve la sesión."""
    r = client.post("/api/v1/cash-sessions/open", json={"opening_float": opening_float, "notes": notes}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def create_product(client, h_admin) -> Callable[..., dict]:
    counter = {"n": 0}

    def _create(**overrides) -> dict:
        counter["n"] += 1
        payload = {"name": f"Producto {counter['n']}", "price": "1000", "initial_stock": 10, **overrides}
        r = client.post("/api/v1/products", json=payload, headers=h_admin)
        assert r.status_code == 201, r.text
        return r.json()

    return _create
