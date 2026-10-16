"""Las migraciones reales (alembic upgrade head) deben coincidir con los modelos."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

EXPECTED_TABLES = {
    "users", "plans", "members", "memberships", "payments", "body_measurements",
    "cash_sessions", "products", "inventory_movements", "sales", "sale_items", "document_sequences",
}


def test_existe_una_sola_clase_base():
    """Regresión: había dos Base y Alembic leía la vacía (autogenerate -> DROP TABLE de todo)."""
    from app.db.session import Base as desde_session
    from app.models.base import Base as desde_modelos
    assert desde_session is desde_modelos


def test_metadata_registra_todas_las_tablas():
    import app.models  # noqa: F401
    from app.models.base import Base
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_las_migraciones_coinciden_exactamente_con_los_modelos(test_engine):
    from app.models.base import Base
    with test_engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], f"Desvíos entre modelos y migraciones: {diff}"


def test_la_bd_de_pruebas_esta_en_la_ultima_revision(test_engine):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.tests.conftest import BACKEND_DIR
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with test_engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == head


def test_unaccent_disponible_y_roles_sincronizados(test_engine):
    with test_engine.connect() as conn:
        assert conn.scalar(text("SELECT unaccent('José Muñoz')")) == "Jose Munoz"
        roles = conn.scalar(text("SELECT array_agg(e::text) FROM unnest(enum_range(NULL::user_role)) e"))
    assert set(roles) == {"admin", "receptionist", "trainer", "member"}


def test_migracion_0006_baja_y_sube_limpia(test_engine):
    """downgrade → upgrade de la 0006 sobre la BD de pruebas (sin datos de otras pruebas)."""
    import os
    from alembic import command
    from alembic.config import Config
    from app.tests.conftest import BACKEND_DIR
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    assert os.environ.get("ALEMBIC_DATABASE_URL")
    command.downgrade(cfg, "0005_multi_gym_payments")
    with test_engine.connect() as conn:
        assert conn.scalar(text("SELECT to_regclass('public.sales')")) is None
    command.upgrade(cfg, "head")
    with test_engine.connect() as conn:
        assert conn.scalar(text("SELECT to_regclass('public.sales')")) == "sales"
    from app.tests.conftest import remove_seeded_plans
    remove_seeded_plans(test_engine)


def test_migracion_0007_siembra_los_planes_oficiales_sin_duplicar(test_engine):
    """La semilla crea Pase de Día / Quincena / Mensualidad y, si ya existe un equivalente, lo actualiza."""
    from alembic import command
    from alembic.config import Config
    from app.tests.conftest import BACKEND_DIR, remove_seeded_plans
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.downgrade(cfg, "0006_cash_sessions_pos")
    with test_engine.begin() as conn:   # un plan "Mensual" previo a ₡25 000 e inactivo
        conn.execute(text(
            "INSERT INTO plans (id, gym_id, name, duration_days, price, is_active) "
            "SELECT gen_random_uuid(), id, 'Mensual', 31, 25000, false FROM gyms WHERE slug = 'lion-fitness-center'"
        ))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0006_cash_sessions_pos")      # la semilla es idempotente:
    command.upgrade(cfg, "head")                          # correrla dos veces no duplica
    with test_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT p.name, p.duration_days, p.price, p.tax_rate, p.is_active FROM plans p JOIN gyms g ON g.id = p.gym_id "
            "WHERE g.slug = 'lion-fitness-center' ORDER BY p.duration_days"
        )).all()
        msg = conn.scalar(text("SELECT overdue_message FROM gyms WHERE slug = 'lion-fitness-center'"))
    assert [(r[0], r[1], str(r[2]), str(r[3]), r[4]) for r in rows] == [
        ("Pase de Día", 1, "2000.00", "13.00", True),
        ("Quincena", 15, "13000.00", "13.00", True),
        ("Mensualidad", 30, "20000.00", "13.00", True),          # "Mensual" se actualizó, no se duplicó
    ]
    assert "{nombre}" in msg and "{fecha_vencimiento}" in msg
    remove_seeded_plans(test_engine)
