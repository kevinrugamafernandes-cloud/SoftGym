import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class GymScopedMixin:
    """
    Multi-sucursal / multi-gimnasio (SaaS): toda fila de negocio pertenece a un gimnasio.
    Los repositorios filtran SIEMPRE por el gym_id del usuario autenticado (tomado de la BD,
    no del token), de modo que un gimnasio nunca ve ni modifica datos de otro.
    """
    gym_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gyms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
