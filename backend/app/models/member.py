"""
Modelo de Socio (Member).

Representa a cada persona inscrita en Lion Fitness Center.
La cédula (identification) es el identificador natural único:
se usa para la búsqueda rápida y el autocompletado con el
Registro Civil de Costa Rica.
"""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, Enum as SQLEnum, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin, SoftDeleteMixin, TimestampMixin
from app.models.enums import Gender, MemberStatus

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.body_measurement import BodyMeasurement


class Member(Base, TimestampMixin, SoftDeleteMixin, GymScopedMixin):
    __tablename__ = "members"

    # ── Identificación ────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    identification: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # ── Datos personales ──────────────────────────────────────────────────────
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[Gender]] = mapped_column(
        SQLEnum(
            Gender,
            name="gender_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=True,
        ),
        nullable=True,
    )

    # ── Contacto ──────────────────────────────────────────────────────────────
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # ── Estado ────────────────────────────────────────────────────────────────
    status: Mapped[MemberStatus] = mapped_column(
        SQLEnum(
            MemberStatus,
            name="member_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=True,
        ),
        nullable=False,
        default=MemberStatus.ACTIVE,
        index=True,
    )
    joined_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Relaciones ────────────────────────────────────────────────────────────
    memberships: Mapped[List["Membership"]] = relationship(
        "Membership",
        back_populates="member",
        cascade="all, delete-orphan",
        order_by="desc(Membership.created_at)",
    )
    body_measurements: Mapped[List["BodyMeasurement"]] = relationship(
        "BodyMeasurement",
        back_populates="member",
        cascade="all, delete-orphan",
        order_by="desc(BodyMeasurement.recorded_at)",
    )

    # ── Índices compuestos ────────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("gym_id", "identification", name="uq_members_gym_identification"),
        Index("ix_members_full_name", "first_name", "last_name"),
        Index("ix_members_status_deleted", "status", "is_deleted"),
    )

    # ── Propiedades calculadas ────────────────────────────────────────────────
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Member id={self.id} cedula={self.identification} name={self.full_name}>"
