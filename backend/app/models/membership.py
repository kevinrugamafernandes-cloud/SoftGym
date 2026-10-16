"""
Modelo de Membresía.

Representa la suscripción activa (o histórica) de un Socio a un Plan.
Cada pago exitoso extiende o crea una nueva membresía.
Un socio puede tener múltiples membresías históricas; la vigente es
la de mayor end_date que no esté cancelada.
"""
import uuid
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Enum as SQLEnum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.plan import Plan
    from app.models.payment import Payment


class MembershipStatus(str, Enum):
    ACTIVE = "activa"
    EXPIRED = "vencida"
    CANCELLED = "cancelada"


class Membership(Base, TimestampMixin, GymScopedMixin):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Claves foráneas ───────────────────────────────────────────────────────
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Vigencia ──────────────────────────────────────────────────────────────
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        SQLEnum(
            MembershipStatus,
            name="membership_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=True,
        ),
        nullable=False,
        default=MembershipStatus.ACTIVE,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relaciones ────────────────────────────────────────────────────────────
    member: Mapped["Member"] = relationship("Member", back_populates="memberships")
    plan: Mapped["Plan"] = relationship("Plan", back_populates="memberships")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="membership",
        cascade="save-update, merge",  # los pagos son financieros: nunca se borran en cascada
    )

    __table_args__ = (
        Index("ix_memberships_member_end", "member_id", "end_date"),
        Index("ix_memberships_status_end", "status", "end_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Membership id={self.id} member={self.member_id} "
            f"end={self.end_date} status={self.status}>"
        )
