"""rutinler tablosu ve tasks rutin_id sabit_saat

Yeni `rutinler` tablosu (tekrarlayan görev şablonları) ve `tasks`'a
`rutin_id` (materyalize edilen görevi kaynak rutine bağlar) ile `sabit_saat`
(rutin görevinin o gün tam hangi saatte yerleşmesi gerektiği) eklenir.
Taşınacak eski veri yok — bunlar tamamen yeni kavramlar.

SQLite ALTER TABLE ile foreign key eklemeyi desteklemediği için
`tasks.rutin_id` foreign key'i `op.batch_alter_table` (kopyala-taşı) ile
ekleniyor (Faz 2'deki unique constraint migration'ıyla aynı yöntem).

Revision ID: 2dcdb96ac2d2
Revises: ff0b6f3d07e9
Create Date: 2026-07-30 15:46:10.754758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2dcdb96ac2d2'
down_revision: Union[str, Sequence[str], None] = 'ff0b6f3d07e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rutinler',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('baslik', sa.String(length=200), nullable=False),
        sa.Column('gunler', sa.JSON(), nullable=False),
        sa.Column('saat', sa.Time(), nullable=False),
        sa.Column('sure_dakika', sa.Integer(), nullable=False),
        sa.Column('oncelik', sa.Integer(), nullable=False),
        sa.Column('aktif', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('tasks', sa.Column('rutin_id', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('sabit_saat', sa.Time(), nullable=True))

    with op.batch_alter_table('tasks') as batch_op:
        batch_op.create_foreign_key(
            'fk_tasks_rutin_id', 'rutinler', ['rutin_id'], ['id'], ondelete='SET NULL'
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_constraint('fk_tasks_rutin_id', type_='foreignkey')

    op.drop_column('tasks', 'sabit_saat')
    op.drop_column('tasks', 'rutin_id')
    op.drop_table('rutinler')
