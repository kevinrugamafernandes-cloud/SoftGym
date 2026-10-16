from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Única fuente de verdad de Base: la definida junto a los modelos.
# (Antes existía una segunda clase Base aquí con metadata vacío, y Alembic
# la leía en lugar de la real -> autogenerate veía "todas las tablas removidas".)
from app.models.base import Base  # noqa: F401

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
