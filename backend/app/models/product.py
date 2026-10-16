"""
Productos de la tienda del gimnasio (bebidas, suplementos, snacks) e inventario.

El stock NUNCA se edita a mano: cambia solo por movimientos (entrada, venta, ajuste,
anulación), cada uno registrado en `inventory_movements` con el saldo resultante.
La base de datos impide stock negativo (CHECK) como última línea de defensa.

Precios: `price` es el precio FINAL al consumidor, con IVA incluido (en Costa Rica el
precio exhibido debe incluir impuestos). El desglose se calcula en cada venta.
`cabys_code` queda preparado para la factura electrónica 4.4 (cada línea exige CABYS).
"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GymScopedMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Product(Base, TimestampMixin, GymScopedMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)          # código interno / de barras
    category: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)          # IVA incluido
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)  # costo unitario (margen)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("13.00"))
    cabys_code: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)      # alerta de stock bajo
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
        CheckConstraint("min_stock >= 0", name="ck_products_min_stock"),
        CheckConstraint("price >= 0", name="ck_products_price"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_products_tax_rate"),
        UniqueConstraint("gym_id", "sku", name="uq_products_gym_sku"),
        # Exacto en la BD; el servicio además lo valida sin distinguir mayúsculas (igual que los planes).
        UniqueConstraint("gym_id", "name", name="uq_products_gym_name"),
    )


class MovementKind(str, Enum):
    INITIAL = "inicial"           # inventario inicial al crear el producto
    PURCHASE = "entrada"          # compra / reposición
    SALE = "venta"
    SALE_VOID = "anulacion_venta"
    ADJUSTMENT = "ajuste"         # conteo físico, merma, vencimiento


class InventoryMovement(Base, GymScopedMixin):
    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False,
    )
    kind: Mapped[MovementKind] = mapped_column(
        SQLEnum(MovementKind, name="inventory_movement_kind_enum",
                values_callable=lambda obj: [e.value for e in obj], native_enum=True),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)      # con signo: + entra, − sale
    stock_after: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    sale_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    # clock_timestamp(), no now(): now() es la hora de INICIO de la transacción y dos movimientos de
    # la misma venta quedarían con la misma hora; la bitácora necesita un orden estable.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False,
    )

    product: Mapped["Product"] = relationship("Product")
    user: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        CheckConstraint("quantity <> 0", name="ck_inventory_movements_quantity"),
        CheckConstraint("stock_after >= 0", name="ck_inventory_movements_stock_after"),
        Index("ix_inventory_movements_product_created", "product_id", "created_at"),
    )
