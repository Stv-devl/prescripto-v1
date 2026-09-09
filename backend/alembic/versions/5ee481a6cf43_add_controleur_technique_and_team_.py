"""add controleur_technique and team addresses to projects

Revision ID: 5ee481a6cf43
Revises: 9c81289794d2
Create Date: 2026-03-05 09:21:44.561262
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5ee481a6cf43'
down_revision: str | None = '9c81289794d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('architect_address', sa.String(length=500), server_default='', nullable=False))
    op.add_column('projects', sa.Column('bureau_thermique_address', sa.String(length=500), server_default='', nullable=False))
    op.add_column('projects', sa.Column('bureau_vrd_address', sa.String(length=500), server_default='', nullable=False))
    op.add_column('projects', sa.Column('bureau_beton_address', sa.String(length=500), server_default='', nullable=False))
    op.add_column('projects', sa.Column('economiste_address', sa.String(length=500), server_default='', nullable=False))
    op.add_column('projects', sa.Column('controleur_technique_address', sa.String(length=500), server_default='', nullable=False))


def downgrade() -> None:
    op.drop_column('projects', 'controleur_technique_address')
    op.drop_column('projects', 'economiste_address')
    op.drop_column('projects', 'bureau_beton_address')
    op.drop_column('projects', 'bureau_vrd_address')
    op.drop_column('projects', 'bureau_thermique_address')
    op.drop_column('projects', 'architect_address')
