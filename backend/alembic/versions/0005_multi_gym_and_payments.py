"""multi-gimnasio (gym_id), comprobantes y anulación de pagos

- Crea `gyms` e inserta el gimnasio por defecto (Lion Fitness Center).
- Agrega `gym_id` (NOT NULL, FK, índice) a users, plans, members, memberships, payments,
  body_measurements. Las filas EXISTENTES se asignan al gimnasio por defecto.
- Unicidad por gimnasio: members(gym_id, identification) y plans(gym_id, name).
- payments: receipt_number (consecutivo por gimnasio), list_price y anulación (voided_*).
  La FK payments.membership_id pasa de CASCADE a RESTRICT: un pago nunca se borra en cascada.
- Crea `receipt_sequences` (contador de comprobantes por gimnasio).

Revision ID: 0005_multi_gym_payments
Revises: 0004_unaccent
Create Date: 2026-10-08 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_multi_gym_payments"
down_revision: Union[str, None] = "0004_unaccent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
TABLES = ("users", "plans", "members", "memberships", "payments", "body_measurements")


def upgrade() -> None:
    # ── gyms + gimnasio por defecto ───────────────────────────────────────────
    op.create_table(
        "gyms",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Costa_Rica"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CRC"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_gyms_slug", "gyms", ["slug"], unique=True)
    op.execute(
        "INSERT INTO gyms (name, slug) VALUES ('Lion Fitness Center', 'lion-fitness-center')"
    )

    # ── gym_id en las tablas de negocio (las filas existentes → gimnasio por defecto) ──
    for table in TABLES:
        op.add_column(table, sa.Column("gym_id", UUID, nullable=True))
        op.execute(f"UPDATE {table} SET gym_id = (SELECT id FROM gyms ORDER BY created_at, id LIMIT 1)")
        op.alter_column(table, "gym_id", nullable=False)
        op.create_foreign_key(f"fk_{table}_gym_id", table, "gyms", ["gym_id"], ["id"], ondelete="RESTRICT")
        op.create_index(f"ix_{table}_gym_id", table, ["gym_id"])

    # ── unicidad por gimnasio ─────────────────────────────────────────────────
    op.drop_index("ix_members_identification", table_name="members")
    op.create_index("ix_members_identification", "members", ["identification"])
    op.create_unique_constraint("uq_members_gym_identification", "members", ["gym_id", "identification"])

    op.drop_constraint("uq_plans_name", "plans", type_="unique")
    op.create_unique_constraint("uq_plans_gym_name", "plans", ["gym_id", "name"])

    # ── payments: comprobante, precio de lista y anulación ────────────────────
    op.add_column("payments", sa.Column("receipt_number", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("list_price", sa.Numeric(10, 2), nullable=True))
    op.add_column("payments", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("voided_by_id", UUID, nullable=True))
    op.add_column("payments", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_foreign_key("fk_payments_voided_by_id", "payments", "users", ["voided_by_id"], ["id"], ondelete="SET NULL")

    op.execute(
        """
        UPDATE payments p SET receipt_number = r.rn
        FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY gym_id ORDER BY created_at, id) AS rn FROM payments) r
        WHERE p.id = r.id
        """
    )
    op.alter_column("payments", "receipt_number", nullable=False)
    op.create_unique_constraint("uq_payments_gym_receipt", "payments", ["gym_id", "receipt_number"])
    op.create_index("ix_payments_gym_date", "payments", ["gym_id", "payment_date"])

    # Un pago jamás debe desaparecer por borrar una membresía: CASCADE → RESTRICT
    op.drop_constraint("payments_membership_id_fkey", "payments", type_="foreignkey")
    op.create_foreign_key(
        "payments_membership_id_fkey", "payments", "memberships", ["membership_id"], ["id"], ondelete="RESTRICT"
    )

    # ── contador de comprobantes por gimnasio ─────────────────────────────────
    op.create_table(
        "receipt_sequences",
        sa.Column("gym_id", UUID, primary_key=True, nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["gym_id"], ["gyms.id"], ondelete="RESTRICT"),
    )
    op.execute(
        """
        INSERT INTO receipt_sequences (gym_id, last_number)
        SELECT g.id, COALESCE((SELECT MAX(p.receipt_number) FROM payments p WHERE p.gym_id = g.id), 0)
        FROM gyms g
        """
    )


def downgrade() -> None:
    op.drop_table("receipt_sequences")

    op.drop_constraint("payments_membership_id_fkey", "payments", type_="foreignkey")
    op.create_foreign_key(
        "payments_membership_id_fkey", "payments", "memberships", ["membership_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_index("ix_payments_gym_date", table_name="payments")
    op.drop_constraint("uq_payments_gym_receipt", "payments", type_="unique")
    op.drop_constraint("fk_payments_voided_by_id", "payments", type_="foreignkey")
    for col in ("void_reason", "voided_by_id", "voided_at", "list_price", "receipt_number"):
        op.drop_column("payments", col)

    op.drop_constraint("uq_plans_gym_name", "plans", type_="unique")
    op.create_unique_constraint("uq_plans_name", "plans", ["name"])
    op.drop_constraint("uq_members_gym_identification", "members", type_="unique")
    op.drop_index("ix_members_identification", table_name="members")
    op.create_index("ix_members_identification", "members", ["identification"], unique=True)

    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_gym_id", table_name=table)
        op.drop_constraint(f"fk_{table}_gym_id", table, type_="foreignkey")
        op.drop_column(table, "gym_id")

    op.drop_index("ix_gyms_slug", table_name="gyms")
    op.drop_table("gyms")
