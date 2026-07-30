"""gunluk enerji tablosu ve plan kayitlarina enerji seviyesi

Yeni `gunluk_enerji` tablosu (kullanıcının gün bazlı enerji/ruh hali seçimi)
ve `plan_kayitlari.enerji_seviyesi` (o planın hangi enerjiyle üretildiği,
nullable) eklenir. Taşınacak eski veri yok — tamamen yeni kavramlar.

Revision ID: a82a61b2a2ab
Revises: 6fdaf2550579
Create Date: 2026-07-30 17:33:07.736999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a82a61b2a2ab'
down_revision: Union[str, Sequence[str], None] = '6fdaf2550579'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'gunluk_enerji',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gun', sa.Date(), nullable=False),
        sa.Column('seviye', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'gun', name='uq_gunluk_enerji_user_gun'),
    )
    op.add_column('plan_kayitlari', sa.Column('enerji_seviyesi', sa.String(length=10), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('plan_kayitlari', 'enerji_seviyesi')
    op.drop_table('gunluk_enerji')
