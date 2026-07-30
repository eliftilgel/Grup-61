"""haftalik bloklar tablosu ve profil buffer dakika

Yeni `haftalik_bloklar` tablosu (kalıcı, haftalık tekrar eden sabit kapalı/serbest
zaman blokları) ve `profil.buffer_dakika` (görevler arası tampon dakika, mevcut
satırlar için varsayılan 0) eklenir. Taşınacak eski veri yok — tamamen yeni kavramlar.

Revision ID: 7c1cf5914b88
Revises: 2dcdb96ac2d2
Create Date: 2026-07-30 16:14:55.519936

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1cf5914b88'
down_revision: Union[str, Sequence[str], None] = '2dcdb96ac2d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'haftalik_bloklar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tur', sa.String(length=15), nullable=False),
        sa.Column('gun', sa.Integer(), nullable=False),
        sa.Column('baslangic', sa.Time(), nullable=False),
        sa.Column('bitis', sa.Time(), nullable=False),
        sa.Column('etiket', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('profil', sa.Column('buffer_dakika', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('profil', 'buffer_dakika')
    op.drop_table('haftalik_bloklar')
