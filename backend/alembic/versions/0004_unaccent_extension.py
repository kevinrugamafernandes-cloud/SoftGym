"""habilita la extensión unaccent (búsqueda de socios sin distinguir tildes)

Permite que buscar "jose" encuentre "José" y "munoz" encuentre "Muñoz".
`unaccent` es una extensión "trusted" desde PostgreSQL 13: la puede crear el
dueño de la base sin ser superusuario (también disponible en Supabase).

Revision ID: 0004_unaccent
Revises: 0003_sync_users
Create Date: 2026-09-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_unaccent"
down_revision: Union[str, None] = "0003_sync_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    # No se elimina: otras partes de la base podrían depender de la extensión.
    pass
