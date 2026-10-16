"""fase 2: members, plans, memberships, payments, body_measurements

Revision ID: 0002_members_plans
Revises: 0001_initial
Create Date: 2026-09-29 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_members_plans"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *values: str) -> postgresql.ENUM:
    """ENUM ya creado aparte: las columnas no deben intentar crearlo de nuevo."""
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # ── Tipos ENUM ────────────────────────────────────────────────────────────
    postgresql.ENUM(
        "masculino", "femenino", "otro", "prefiero_no_decir", name="gender_enum"
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "activo", "por_vencer", "moroso", "inactivo", name="member_status_enum"
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "activa", "vencida", "cancelada", name="membership_status_enum"
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "efectivo", "tarjeta", "transferencia", "sinpe", "otro", name="payment_method_enum"
    ).create(bind, checkfirst=True)

    # ── plans ─────────────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_plans_name"),
        sa.CheckConstraint("duration_days > 0", name="ck_plans_duration_positive"),
        sa.CheckConstraint("price >= 0", name="ck_plans_price_non_negative"),
    )
    op.create_index("ix_plans_is_active", "plans", ["is_active"])

    # ── members ───────────────────────────────────────────────────────────────
    op.create_table(
        "members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("identification", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", _enum("gender_enum", "masculino", "femenino", "otro",
                                  "prefiero_no_decir"), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("status", _enum("member_status_enum", "activo", "por_vencer",
                                  "moroso", "inactivo"),
                  nullable=False, server_default="activo"),
        sa.Column("joined_at", sa.Date(), nullable=False,
                  server_default=sa.text("CURRENT_DATE")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_members_identification", "members", ["identification"], unique=True)
    op.create_index("ix_members_email", "members", ["email"])
    op.create_index("ix_members_status", "members", ["status"])
    op.create_index("ix_members_is_deleted", "members", ["is_deleted"])
    op.create_index("ix_members_full_name", "members", ["first_name", "last_name"])
    op.create_index("ix_members_status_deleted", "members", ["status", "is_deleted"])

    # ── memberships ───────────────────────────────────────────────────────────
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", _enum("membership_status_enum", "activa", "vencida",
                                  "cancelada"),
                  nullable=False, server_default="activa"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("end_date >= start_date", name="ck_memberships_dates"),
    )
    op.create_index("ix_memberships_member_id", "memberships", ["member_id"])
    op.create_index("ix_memberships_end_date", "memberships", ["end_date"])
    op.create_index("ix_memberships_status", "memberships", ["status"])
    op.create_index("ix_memberships_member_end", "memberships", ["member_id", "end_date"])
    op.create_index("ix_memberships_status_end", "memberships", ["status", "end_date"])

    # ── payments ──────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("registered_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False,
                  server_default=sa.text("CURRENT_DATE")),
        sa.Column("method", _enum("payment_method_enum", "efectivo", "tarjeta",
                                  "transferencia", "sinpe", "otro"),
                  nullable=False, server_default="efectivo"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["registered_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
    )
    op.create_index("ix_payments_membership_id", "payments", ["membership_id"])
    op.create_index("ix_payments_payment_date", "payments", ["payment_date"])

    # ── body_measurements ─────────────────────────────────────────────────────
    op.create_table(
        "body_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("bmi", sa.Numeric(5, 2), nullable=True),
        sa.Column("body_fat_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("muscle_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("chest_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("waist_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("hips_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("arms_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("thighs_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("calves_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_body_measurements_member_id", "body_measurements", ["member_id"])
    op.create_index("ix_body_measurements_recorded_at", "body_measurements", ["recorded_at"])


def downgrade() -> None:
    op.drop_table("body_measurements")
    op.drop_table("payments")
    op.drop_table("memberships")
    op.drop_table("members")
    op.drop_table("plans")

    bind = op.get_bind()
    for name in ("payment_method_enum", "membership_status_enum",
                 "member_status_enum", "gender_enum"):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
