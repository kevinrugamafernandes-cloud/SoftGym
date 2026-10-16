"""configuración del negocio, IVA de membresías, cierre mensual, recordatorios y planes oficiales

- gyms: razón social, cédula, WhatsApp comercial, correo, dirección y mensajes personalizables
  (se precargan los mensajes por defecto).
- plans.tax_rate y payments.tax_rate (13 %): las membresías son un servicio gravado; el pago guarda
  la tarifa vigente al cobrar. Los pagos existentes quedan al 13 % (precio con IVA incluido).
- monthly_closes: cierre mensual con instantánea de totales; bloquea el periodo.
- member_reminders: bitácora de recordatorios de cobro por WhatsApp.
- Planes oficiales: Pase de Día ₡2 000, Quincena ₡13 000, Mensualidad ₡20 000 (activos). Si ya
  existe un plan equivalente (p. ej. "Mensual"), se actualiza en lugar de duplicarlo.

Revision ID: 0007_settings_tax_closes
Revises: 0006_cash_sessions_pos
Create Date: 2026-10-16 12:00:00.000000
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.defaults import (
    DEFAULT_EXPIRING_MESSAGE, DEFAULT_OVERDUE_MESSAGE, DEFAULT_RECEIPT_MESSAGE, OFFICIAL_PLANS,
)

revision: str = "0007_settings_tax_closes"
down_revision: Union[str, None] = "0006_cash_sessions_pos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def seed_official_plans(bind) -> None:
    """Idempotente: crea o actualiza (y activa) los planes oficiales en cada gimnasio."""
    gyms = bind.execute(sa.text("SELECT id FROM gyms")).scalars().all()
    for gym_id in gyms:
        for plan in OFFICIAL_PLANS:
            existing = bind.execute(
                sa.text("SELECT id FROM plans WHERE gym_id = :g AND lower(btrim(name)) = ANY(:names) ORDER BY created_at LIMIT 1"),
                {"g": gym_id, "names": [plan["name"].lower(), *plan["aliases"]]},
            ).scalar()
            params = {
                "g": gym_id, "name": plan["name"], "days": plan["duration_days"], "price": plan["price"],
                "desc": plan["description"],
            }
            if existing:
                # Si otro plan ya usa el nombre oficial exacto, se conserva el nombre actual.
                taken = bind.execute(
                    sa.text("SELECT 1 FROM plans WHERE gym_id = :g AND name = :name AND id <> :id"),
                    {"g": gym_id, "name": plan["name"], "id": existing},
                ).scalar()
                bind.execute(
                    sa.text(
                        "UPDATE plans SET name = CASE WHEN :keep THEN name ELSE :name END, duration_days = :days, "
                        "price = :price, tax_rate = 13, is_active = true, updated_at = now() WHERE id = :id"
                    ),
                    {**params, "id": existing, "keep": bool(taken)},
                )
            else:
                bind.execute(
                    sa.text(
                        "INSERT INTO plans (id, gym_id, name, description, duration_days, price, tax_rate, is_active) "
                        "VALUES (:id, :g, :name, :desc, :days, :price, 13, true)"
                    ),
                    {**params, "id": uuid.uuid4()},
                )


def upgrade() -> None:
    # ── Configuración del negocio ─────────────────────────────────────────────
    for name, type_ in (
        ("legal_name", sa.String(160)), ("tax_id", sa.String(20)), ("whatsapp_phone", sa.String(20)),
        ("email", sa.String(160)), ("address", sa.Text()), ("receipt_message", sa.Text()),
        ("overdue_message", sa.Text()), ("expiring_message", sa.Text()),
    ):
        op.add_column("gyms", sa.Column(name, type_, nullable=True))
    op.execute(
        sa.text(
            "UPDATE gyms SET receipt_message = COALESCE(receipt_message, :r), "
            "overdue_message = COALESCE(overdue_message, :o), expiring_message = COALESCE(expiring_message, :e)"
        ).bindparams(r=DEFAULT_RECEIPT_MESSAGE, o=DEFAULT_OVERDUE_MESSAGE, e=DEFAULT_EXPIRING_MESSAGE)
    )

    # ── IVA de las membresías ─────────────────────────────────────────────────
    op.add_column("plans", sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="13.00"))
    op.add_column("payments", sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="13.00"))
    op.alter_column("plans", "tax_rate", server_default=None)
    op.alter_column("payments", "tax_rate", server_default=None)
    op.create_check_constraint("ck_plans_tax_rate", "plans", "tax_rate >= 0 AND tax_rate <= 100")

    # ── Cierre mensual ────────────────────────────────────────────────────────
    op.create_table(
        "monthly_closes",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("gym_id", UUID, sa.ForeignKey("gyms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("closed_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("gym_id", "year", "month", name="uq_monthly_closes_period"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_monthly_closes_month"),
        sa.CheckConstraint("year BETWEEN 2000 AND 2100", name="ck_monthly_closes_year"),
    )
    op.create_index("ix_monthly_closes_gym_id", "monthly_closes", ["gym_id"])

    # ── Recordatorios por WhatsApp ────────────────────────────────────────────
    op.create_table(
        "member_reminders",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("gym_id", UUID, sa.ForeignKey("gyms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("member_id", UUID, sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("membership_end_date", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("sent_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_member_reminders_gym_id", "member_reminders", ["gym_id"])
    op.create_index("ix_member_reminders_member_created", "member_reminders", ["member_id", "created_at"])

    # ── Planes oficiales ──────────────────────────────────────────────────────
    seed_official_plans(op.get_bind())


def downgrade() -> None:
    # Los planes sembrados se conservan (pueden tener cobros asociados).
    op.drop_table("member_reminders")
    op.drop_table("monthly_closes")
    op.drop_constraint("ck_plans_tax_rate", "plans", type_="check")
    op.drop_column("payments", "tax_rate")
    op.drop_column("plans", "tax_rate")
    for name in ("expiring_message", "overdue_message", "receipt_message", "address", "email",
                 "whatsapp_phone", "tax_id", "legal_name"):
        op.drop_column("gyms", name)
