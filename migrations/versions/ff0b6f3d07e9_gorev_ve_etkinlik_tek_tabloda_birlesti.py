"""gorev ve etkinlik tek tabloda birlesti

tasks tablosuna tur/google_id/start/end/updated eklenir; calendar_events
tablosundaki mevcut satırlar tasks'a tur='etkinlik' olarak taşınır (priority=1,
duration_minutes=0 — etkinlik için anlamsız ama NOT NULL kolonlar; due_date,
start'ın baştaki YYYY-MM-DD parçası ayrıştırılabiliyorsa ondan türetilir,
değilse NULL kalır). Ardından calendar_events silinir ve (user_id, google_id)
üzerinde yeni bir unique constraint eklenir — görev satırlarında google_id hep
NULL olduğu için bu satırlar arasında çakışma olmaz.

SQLite ALTER TABLE ile constraint eklemeyi desteklemediği için unique
constraint `op.batch_alter_table` (kopyala-taşı) ile ekleniyor.

Revision ID: ff0b6f3d07e9
Revises: 02f95e16ce2f
Create Date: 2026-07-30 15:12:47.304609

"""
from datetime import date, datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff0b6f3d07e9'
down_revision: Union[str, Sequence[str], None] = '02f95e16ce2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _due_date_ten_turet(start: str) -> date | None:
    if not start:
        return None
    try:
        return date.fromisoformat(start[:10])
    except ValueError:
        return None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    op.add_column('tasks', sa.Column('tur', sa.String(length=10), nullable=False, server_default='gorev'))
    op.add_column('tasks', sa.Column('google_id', sa.String(length=300), nullable=True))
    op.add_column('tasks', sa.Column('start', sa.String(length=50), nullable=False, server_default=''))
    op.add_column('tasks', sa.Column('end', sa.String(length=50), nullable=False, server_default=''))
    op.add_column('tasks', sa.Column('updated', sa.String(length=50), nullable=False, server_default=''))

    calendar_events = sa.table(
        'calendar_events',
        sa.column('user_id', sa.Integer),
        sa.column('google_id', sa.String),
        sa.column('title', sa.String),
        sa.column('description', sa.String),
        sa.column('start', sa.String),
        sa.column('end', sa.String),
        sa.column('updated', sa.String),
    )
    tasks = sa.table(
        'tasks',
        sa.column('user_id', sa.Integer),
        sa.column('title', sa.String),
        sa.column('description', sa.String),
        sa.column('priority', sa.Integer),
        sa.column('done', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('due_date', sa.Date),
        sa.column('duration_minutes', sa.Integer),
        sa.column('tur', sa.String),
        sa.column('google_id', sa.String),
        sa.column('start', sa.String),
        sa.column('end', sa.String),
        sa.column('updated', sa.String),
    )

    simdi = datetime.now(timezone.utc)
    for e in bind.execute(sa.select(calendar_events)).fetchall():
        bind.execute(
            tasks.insert().values(
                user_id=e.user_id,
                title=e.title,
                description=e.description,
                priority=1,
                done=False,
                created_at=simdi,
                due_date=_due_date_ten_turet(e.start),
                duration_minutes=0,
                tur='etkinlik',
                google_id=e.google_id,
                start=e.start,
                end=e.end,
                updated=e.updated,
            )
        )

    op.drop_table('calendar_events')

    with op.batch_alter_table('tasks') as batch_op:
        batch_op.create_unique_constraint('uq_tasks_user_google', ['user_id', 'google_id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_constraint('uq_tasks_user_google', type_='unique')

    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('google_id', sa.String(length=300), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=False),
        sa.Column('start', sa.String(length=50), nullable=False),
        sa.Column('end', sa.String(length=50), nullable=False),
        sa.Column('updated', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'google_id', name='uq_calendar_events_user_google'),
    )

    bind = op.get_bind()
    tasks = sa.table(
        'tasks',
        sa.column('id', sa.Integer),
        sa.column('user_id', sa.Integer),
        sa.column('title', sa.String),
        sa.column('description', sa.String),
        sa.column('tur', sa.String),
        sa.column('google_id', sa.String),
        sa.column('start', sa.String),
        sa.column('end', sa.String),
        sa.column('updated', sa.String),
    )
    calendar_events = sa.table(
        'calendar_events',
        sa.column('user_id', sa.Integer),
        sa.column('google_id', sa.String),
        sa.column('title', sa.String),
        sa.column('description', sa.String),
        sa.column('start', sa.String),
        sa.column('end', sa.String),
        sa.column('updated', sa.String),
    )
    etkinlik_secimi = sa.select(tasks).where(tasks.c.tur == 'etkinlik')
    for t in bind.execute(etkinlik_secimi).fetchall():
        bind.execute(
            calendar_events.insert().values(
                user_id=t.user_id,
                google_id=t.google_id,
                title=t.title,
                description=t.description,
                start=t.start,
                end=t.end,
                updated=t.updated,
            )
        )
    bind.execute(sa.delete(tasks).where(tasks.c.tur == 'etkinlik'))

    op.drop_column('tasks', 'updated')
    op.drop_column('tasks', 'end')
    op.drop_column('tasks', 'start')
    op.drop_column('tasks', 'google_id')
    op.drop_column('tasks', 'tur')
