from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Única fuente de verdad de Base: la definida junto a los modelos.
# (Antes existía una segunda clase Base aquí con metadata vacío, y Alembic
# la leía en lugar de la real -> autogenerate veía "todas las tablas removidas".)
from app.models.base import Base  # noqa: F401

# Pool pequeño y reutilizable: evita abrir una conexión TLS nueva a Supabase en cada petición.
# pool_pre_ping descarta conexiones que el servidor cerró; pool_recycle las renueva cada 5 min.
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.SQL_ECHO,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
