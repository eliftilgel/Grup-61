"""gorev konum link ve teslim tipi alanlari

tasks tablosuna opsiyonel konum/link, esnek/kesin teslim tipi ve kesin
teslimliler için kesin_bitis (tarih+saat) eklenir. Mevcut satırlar
konum='', link='', teslim_tipi='esnek' ile backfill edilir; kesin_bitis
NULL kalır (geriye dönük olarak hepsi esnek kabul edilir).

Not: autogenerate ayrıca calendar_events üzerinde modelle eşleşmeyen bir
'uq_calendar_events_user_google' unique constraint farkı tespit etti —
bu, bu değişiklikle ilgisiz önceden var olan bir şema sapması olduğu için
buraya dahil edilmedi; ayrı olarak ele alınmalı.

Revision ID: 02f95e16ce2f
Revises: f4041c5d3e59
Create Date: 2026-07-30 14:20:58.888648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02f95e16ce2f'
down_revision: Union[str, Sequence[str], None] = 'f4041c5d3e59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('konum', sa.String(length=300), nullable=False, server_default=''))
    op.add_column('tasks', sa.Column('link', sa.String(length=500), nullable=False, server_default=''))
    op.add_column('tasks', sa.Column('teslim_tipi', sa.String(length=10), nullable=False, server_default='esnek'))
    op.add_column('tasks', sa.Column('kesin_bitis', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tasks', 'kesin_bitis')
    op.drop_column('tasks', 'teslim_tipi')
    op.drop_column('tasks', 'link')
    op.drop_column('tasks', 'konum')
