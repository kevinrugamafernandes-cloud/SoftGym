"""sincroniza users con el modelo actual (full_name 255, roles trainer/member)

Corrige dos desvíos entre 0001_initial y app/models/user.py:
  - users.full_name: VARCHAR(120) -> VARCHAR(255)
  - enum user_role: agrega 'trainer' y 'member' (el modelo UserRole ya los define)

Revision ID: 0003_sync_users
Revises: 0002_members_plans
Create Date: 2026-09-29 00:10:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sync_users"
down_revision: Union[str, None] = "0002_members_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users", "full_name",
        existing_type=sa.String(120), type_=sa.String(255), existing_nullable=False,
    )
    # ADD VALUE es válido dentro de una transacción en PostgreSQL 12+
    # (mientras el valor nuevo no se use en esa misma transacción).
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'trainer'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'member'")


def downgrade() -> None:
    # PostgreSQL no permite quitar valores de un ENUM: 'trainer' y 'member'
    # permanecen en el tipo (son inocuos si ninguna fila los usa).
    op.alter_column(
        "users", "full_name",
        existing_type=sa.String(255), type_=sa.String(120), existing_nullable=False,
    )
