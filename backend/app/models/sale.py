"""
Venta de la tienda (punto de venta).

Como los pagos, una venta es un registro FINANCIERO: no se borra ni se edita, se ANULA
(y la anulación devuelve el stock). Cada línea guarda una instantánea del producto
(nombre, CABYS, precio, tarifa de IVA) para que el comprobante y los libros no cambien
si luego se edita el producto: es la misma información que pedirá la factura 4.4.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    CheckConstraint, Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin, TimestampMixin
from app.models.payment import PaymentMethod

if TYPE_CHECKING:
    from app.models.cash_session import CashSession
    from app.models.member import Member
    from app.models.user import User


class Sale(Base, TimestampMixin, GymScopedMixin):
    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)          # día de negocio del gimnasio
    cash_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_sessions.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    cashier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    # ── Cliente (opcional) ────────────────────────────────────────────────────
    member_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="RESTRICT"), nullable=True, index=True,
    )
    customer_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ── Pago ──────────────────────────────────────────────────────────────────
    method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod, name="payment_method_enum", values_callable=lambda obj: [e.value for e in obj],
                native_enum=True, create_type=False),
        nullable=False,
    )
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)    # sin IVA
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Anulación ─────────────────────────────────────────────────────────────
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    items: Mapped[List["SaleItem"]] = relationship(
        "SaleItem", back_populates="sale", order_by="SaleItem.position", cascade="all, delete-orphan",
    )
    cash_session: Mapped["CashSession"] = relationship("CashSession")
    cashier: Mapped[Optional["User"]] = relationship("User", foreign_keys=[cashier_id])
    voided_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[voided_by_id])
    member: Mapped[Optional["Member"]] = relationship("Member")

    __table_args__ = (
        UniqueConstraint("gym_id", "sale_number", name="uq_sales_gym_number"),
        CheckConstraint("total = subtotal + tax_total", name="ck_sales_total"),
        CheckConstraint("total >= 0 AND subtotal >= 0 AND tax_total >= 0", name="ck_sales_amounts"),
        Index("ix_sales_gym_date", "gym_id", "sale_date"),
    )

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    # Instantánea del producto al vender
    product_name: Mapped[str] = mapped_column(String(120), nullable=False)
    cabys_code: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)    # IVA incluido
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_items_quantity"),
        CheckConstraint("line_total = line_subtotal + line_tax", name="ck_sale_items_total"),
        UniqueConstraint("sale_id", "position", name="uq_sale_items_position"),
    )
