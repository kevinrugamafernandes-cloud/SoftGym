"""
Sesión de caja (turno de un cajero).

La recepcionista ABRE caja con un fondo inicial; mientras está abierta, cada cobro de
membresía y cada venta de la tienda que registra queda ligado a ESTA sesión. Al CERRAR
cuenta el efectivo físico: el sistema calcula lo esperado (fondo + efectivo cobrado) y
guarda el sobrante o faltante. Una sesión cerrada es un registro de auditoría: no se edita.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint, Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Numeric, Text, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class CashSessionStatus(str, Enum):
    OPEN = "abierta"
    CLOSED = "cerrada"


class CashSession(Base, TimestampMixin, GymScopedMixin):
    __tablename__ = "cash_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    status: Mapped[CashSessionStatus] = mapped_column(
        SQLEnum(
            CashSessionStatus, name="cash_session_status_enum",
            values_callable=lambda obj: [e.value for e in obj], native_enum=True,
        ),
        nullable=False, default=CashSessionStatus.OPEN,
    )
    # Día de negocio (zona horaria del gimnasio) en que se abrió: agrupa las sesiones del cierre diario.
    business_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Apertura ──────────────────────────────────────────────────────────────
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_float: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)   # fondo inicial (caja chica)
    opening_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Cierre (instantánea inmutable) ────────────────────────────────────────
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True,
    )
    cash_payments_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    cash_sales_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    expected_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    counted_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)   # contado − esperado
    closing_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cashier: Mapped["User"] = relationship("User", foreign_keys=[cashier_id])
    closed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[closed_by_id])

    __table_args__ = (
        CheckConstraint("opening_float >= 0", name="ck_cash_sessions_opening_float"),
        CheckConstraint("counted_cash IS NULL OR counted_cash >= 0", name="ck_cash_sessions_counted_cash"),
        CheckConstraint(
            "(status = 'abierta' AND closed_at IS NULL) OR (status = 'cerrada' AND closed_at IS NOT NULL "
            "AND counted_cash IS NOT NULL AND expected_cash IS NOT NULL AND difference IS NOT NULL)",
            name="ck_cash_sessions_closed_snapshot",
        ),
        # Un cajero solo puede tener UNA caja abierta a la vez (garantizado por la BD, no solo por código).
        Index(
            "uq_cash_sessions_one_open_per_cashier", "gym_id", "cashier_id",
            unique=True, postgresql_where=text("status = 'abierta'"),
        ),
        Index("ix_cash_sessions_gym_date", "gym_id", "business_date"),
    )

    @property
    def is_open(self) -> bool:
        return self.status == CashSessionStatus.OPEN
