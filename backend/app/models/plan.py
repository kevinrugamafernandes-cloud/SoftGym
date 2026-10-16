"""
Modelo de Plan de Membresía.

Sin valores hardcodeados: el administrador crea, edita y desactiva
planes desde el panel. La arquitectura soporta N tipos de planes
(mensual, trimestral, semestral, anual, clases, etc.) sin cambios
de código.
"""
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.membership import Membership


class Plan(Base, TimestampMixin, GymScopedMixin):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    # IVA del servicio (Costa Rica: 13 % general). El precio es FINAL, con IVA incluido.
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("13.00"))
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("gym_id", "name", name="uq_plans_gym_name"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_plans_tax_rate"),
    )

    # ── Relaciones ────────────────────────────────────────────────────────────
    memberships: Mapped[List["Membership"]] = relationship(
        "Membership",
        back_populates="plan",
    )

    def __repr__(self) -> str:
        return f"<Plan id={self.id} name={self.name} days={self.duration_days} price={self.price}>"
