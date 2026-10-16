"""
Modelo de Pago.

Registra cada cobro. Es un registro FINANCIERO: no se borra ni se edita; se ANULA
(voided_*), conservando quién, cuándo y por qué. Los totales excluyen los pagos anulados.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.user import User


class PaymentMethod(str, Enum):
    CASH = "efectivo"
    CARD = "tarjeta"
    TRANSFER = "transferencia"
    SINPE = "sinpe"
    OTHER = "otro"


class Payment(Base, TimestampMixin, GymScopedMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Claves foráneas ───────────────────────────────────────────────────────
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    registered_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    # Turno de caja en que se cobró (NULL en pagos anteriores a las sesiones de caja).
    cash_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_sessions.id", ondelete="RESTRICT"), nullable=True, index=True,
    )

    # ── Comprobante ───────────────────────────────────────────────────────────
    receipt_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Datos del pago ────────────────────────────────────────────────────────
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    list_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)  # precio del plan al cobrar
    # Tarifa de IVA del plan AL COBRAR (instantánea para el libro de ventas; el monto la incluye).
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("13.00"))
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today, index=True)
    method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(
            PaymentMethod,
            name="payment_method_enum",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=True,
        ),
        nullable=False,
        default=PaymentMethod.CASH,
    )
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Anulación (en lugar de borrado) ───────────────────────────────────────
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relaciones ────────────────────────────────────────────────────────────
    membership: Mapped["Membership"] = relationship("Membership", back_populates="payments")
    registered_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[registered_by_id])
    voided_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[voided_by_id])

    __table_args__ = (
        UniqueConstraint("gym_id", "receipt_number", name="uq_payments_gym_receipt"),
        Index("ix_payments_gym_date", "gym_id", "payment_date"),
    )

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None

    def __repr__(self) -> str:
        return f"<Payment id={self.id} receipt={self.receipt_number} amount={self.amount}>"
