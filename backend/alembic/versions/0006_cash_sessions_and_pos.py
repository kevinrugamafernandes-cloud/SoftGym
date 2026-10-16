"""sesiones de caja y punto de venta (productos, inventario, ventas)

- cash_sessions: turnos de caja con fondo inicial y cierre con arqueo (contado vs. esperado).
  Índice único parcial: un cajero no puede tener dos cajas abiertas.
- payments.cash_session_id: los cobros nuevos quedan ligados al turno (los antiguos, NULL).
- products + inventory_movements: inventario con stock no negativo (CHECK) y bitácora.
- sales + sale_items: ventas con desglose de IVA por línea (instantánea del producto).
- document_sequences: consecutivos por gimnasio y tipo de documento (ventas: "venta").

Revision ID: 0006_cash_sessions_pos
Revises: 0005_multi_gym_payments
Create Date: 2026-10-16 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_cash_sessions_pos"
down_revision: Union[str, None] = "0005_multi_gym_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
SESSION_STATUS = postgresql.ENUM("abierta", "cerrada", name="cash_session_status_enum", create_type=False)
MOVEMENT_KIND = postgresql.ENUM(
    "inicial", "entrada", "venta", "anulacion_venta", "ajuste", name="inventory_movement_kind_enum", create_type=False
)
PAYMENT_METHOD = postgresql.ENUM(
    "efectivo", "tarjeta", "transferencia", "sinpe", "otro", name="payment_method_enum", create_type=False
)


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def _gym_fk(table: str):
    return sa.Column("gym_id", UUID, sa.ForeignKey("gyms.id", ondelete="RESTRICT"), nullable=False)


def upgrade() -> None:
    bind = op.get_bind()
    SESSION_STATUS.create(bind, checkfirst=True)
    MOVEMENT_KIND.create(bind, checkfirst=True)

    # ── Sesiones de caja ──────────────────────────────────────────────────────
    op.create_table(
        "cash_sessions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        _gym_fk("cash_sessions"),
        sa.Column("cashier_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", SESSION_STATUS, nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opening_float", sa.Numeric(12, 2), nullable=False),
        sa.Column("opening_notes", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("cash_payments_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_sales_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("counted_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("difference", sa.Numeric(12, 2), nullable=True),
        sa.Column("closing_notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("opening_float >= 0", name="ck_cash_sessions_opening_float"),
        sa.CheckConstraint("counted_cash IS NULL OR counted_cash >= 0", name="ck_cash_sessions_counted_cash"),
        sa.CheckConstraint(
            "(status = 'abierta' AND closed_at IS NULL) OR (status = 'cerrada' AND closed_at IS NOT NULL "
            "AND counted_cash IS NOT NULL AND expected_cash IS NOT NULL AND difference IS NOT NULL)",
            name="ck_cash_sessions_closed_snapshot",
        ),
    )
    op.create_index("ix_cash_sessions_gym_id", "cash_sessions", ["gym_id"])
    op.create_index("ix_cash_sessions_cashier_id", "cash_sessions", ["cashier_id"])
    op.create_index("ix_cash_sessions_gym_date", "cash_sessions", ["gym_id", "business_date"])
    op.create_index(
        "uq_cash_sessions_one_open_per_cashier", "cash_sessions", ["gym_id", "cashier_id"],
        unique=True, postgresql_where=sa.text("status = 'abierta'"),
    )

    op.add_column("payments", sa.Column("cash_session_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_payments_cash_session_id", "payments", "cash_sessions", ["cash_session_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_payments_cash_session_id", "payments", ["cash_session_id"])

    # ── Productos ─────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        _gym_fk("products"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sku", sa.String(40), nullable=True),
        sa.Column("category", sa.String(60), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("cabys_code", sa.String(13), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("min_stock", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
        sa.CheckConstraint("min_stock >= 0", name="ck_products_min_stock"),
        sa.CheckConstraint("price >= 0", name="ck_products_price"),
        sa.CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_products_tax_rate"),
        sa.UniqueConstraint("gym_id", "sku", name="uq_products_gym_sku"),
        sa.UniqueConstraint("gym_id", "name", name="uq_products_gym_name"),
    )
    op.create_index("ix_products_gym_id", "products", ["gym_id"])

    # ── Ventas ────────────────────────────────────────────────────────────────
    op.create_table(
        "sales",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        _gym_fk("sales"),
        sa.Column("sale_number", sa.Integer(), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("cash_session_id", UUID, sa.ForeignKey("cash_sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cashier_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("member_id", UUID, sa.ForeignKey("members.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("customer_name", sa.String(160), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("method", PAYMENT_METHOD, nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("gym_id", "sale_number", name="uq_sales_gym_number"),
        sa.CheckConstraint("total = subtotal + tax_total", name="ck_sales_total"),
        sa.CheckConstraint("total >= 0 AND subtotal >= 0 AND tax_total >= 0", name="ck_sales_amounts"),
    )
    op.create_index("ix_sales_gym_id", "sales", ["gym_id"])
    op.create_index("ix_sales_gym_date", "sales", ["gym_id", "sale_date"])
    op.create_index("ix_sales_cash_session_id", "sales", ["cash_session_id"])
    op.create_index("ix_sales_member_id", "sales", ["member_id"])

    op.create_table(
        "sale_items",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("sale_id", UUID, sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_name", sa.String(120), nullable=False),
        sa.Column("cabys_code", sa.String(13), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("line_subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_tax", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sale_items_quantity"),
        sa.CheckConstraint("line_total = line_subtotal + line_tax", name="ck_sale_items_total"),
        sa.UniqueConstraint("sale_id", "position", name="uq_sale_items_position"),
    )
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("ix_sale_items_product_id", "sale_items", ["product_id"])

    # ── Bitácora de inventario ────────────────────────────────────────────────
    op.create_table(
        "inventory_movements",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        _gym_fk("inventory_movements"),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", MOVEMENT_KIND, nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("sale_id", UUID, sa.ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("quantity <> 0", name="ck_inventory_movements_quantity"),
        sa.CheckConstraint("stock_after >= 0", name="ck_inventory_movements_stock_after"),
    )
    op.create_index("ix_inventory_movements_gym_id", "inventory_movements", ["gym_id"])
    op.create_index("ix_inventory_movements_product_created", "inventory_movements", ["product_id", "created_at"])

    # ── Consecutivos por tipo de documento ────────────────────────────────────
    op.create_table(
        "document_sequences",
        sa.Column("gym_id", UUID, sa.ForeignKey("gyms.id", ondelete="RESTRICT"), primary_key=True, nullable=False),
        sa.Column("doc_type", sa.String(20), primary_key=True, nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("document_sequences")
    op.drop_table("inventory_movements")
    op.drop_table("sale_items")
    op.drop_table("sales")
    op.drop_table("products")
    op.drop_index("ix_payments_cash_session_id", table_name="payments")
    op.drop_constraint("fk_payments_cash_session_id", "payments", type_="foreignkey")
    op.drop_column("payments", "cash_session_id")
    op.drop_table("cash_sessions")
    bind = op.get_bind()
    MOVEMENT_KIND.drop(bind, checkfirst=True)
    SESSION_STATUS.drop(bind, checkfirst=True)
