"""control de descuentos y devoluciones de efectivo tras el cierre de caja

- gyms.max_reception_discount_pct: descuento máximo (%) que puede aplicar la recepción en un
  cobro de membresía. Por defecto 10 %. El administrador no tiene tope.
- payments.void_cash_session_id / sales.void_cash_session_id: caja ABIERTA de la que salió el
  efectivo devuelto al anular un cobro o una venta cuya caja original ya estaba cerrada.
- cash_sessions.cash_refunds_total: instantánea al cierre del efectivo devuelto en el turno.

Revision ID: 0008_discounts_refunds
Revises: 0007_settings_tax_closes
Create Date: 2026-11-06 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_discounts_refunds"
down_revision: Union[str, None] = "0007_settings_tax_closes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "gyms",
        sa.Column("max_reception_discount_pct", sa.Numeric(5, 2), nullable=False, server_default="10"),
    )
    op.create_check_constraint(
        "ck_gyms_max_reception_discount_pct", "gyms",
        "max_reception_discount_pct >= 0 AND max_reception_discount_pct <= 100",
    )
    for table in ("payments", "sales"):
        op.add_column(table, sa.Column("void_cash_session_id", UUID, nullable=True))
        op.create_foreign_key(
            f"fk_{table}_void_cash_session_id", table, "cash_sessions",
            ["void_cash_session_id"], ["id"], ondelete="RESTRICT",
        )
        op.create_index(f"ix_{table}_void_cash_session_id", table, ["void_cash_session_id"])
    op.add_column("cash_sessions", sa.Column("cash_refunds_total", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("cash_sessions", "cash_refunds_total")
    for table in ("payments", "sales"):
        op.drop_index(f"ix_{table}_void_cash_session_id", table_name=table)
        op.drop_constraint(f"fk_{table}_void_cash_session_id", table, type_="foreignkey")
        op.drop_column(table, "void_cash_session_id")
    op.drop_constraint("ck_gyms_max_reception_discount_pct", "gyms", type_="check")
    op.drop_column("gyms", "max_reception_discount_pct")
