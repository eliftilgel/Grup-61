"""plan kayitlarina strateji alani

`plan_kayitlari.strateji` — planın hangi sıralama stratejisiyle (oncelik_agirlikli/
sabah_yogun/dengeli_dagitim) üretildiğini saklar, nullable, taşınacak veri yok.

Revision ID: c53e589a9586
Revises: a82a61b2a2ab
Create Date: 2026-07-30 20:58:19.837929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c53e589a9586'
down_revision: Union[str, Sequence[str], None] = 'a82a61b2a2ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('plan_kayitlari', sa.Column('strateji', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('plan_kayitlari', 'strateji')
