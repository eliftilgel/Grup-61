"""coklu_kullanici_sistemi

users tablosu oluşturulur; varsayılan bir admin hesabı eklenir
(kullanıcı adı "admin", geçici parola "admin123" — admin panelinden
ilk girişte değiştirilmeli); tasks/calendar_events/plan_kayitlari/profil
tablolarına user_id eklenir ve mevcut tüm satırlar admin hesabına
backfill edilir. SQLite'ta ALTER TABLE ile NOT NULL/FK eklemek
desteklenmediği için batch_alter_table (tabloyu yeniden oluşturur)
kullanılır.

Revision ID: f4041c5d3e59
Revises: 7d45f9b9fe21
Create Date: 2026-07-28 11:14:06.318460

"""
from datetime import datetime, timezone
from typing import Sequence, Union

import bcrypt
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4041c5d3e59'
down_revision: Union[str, Sequence[str], None] = '7d45f9b9fe21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VARSAYILAN_ADMIN_KULLANICI_ADI = "admin"
VARSAYILAN_ADMIN_PAROLA = "admin123"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )

    baglanti = op.get_bind()
    admin_hash = bcrypt.hashpw(VARSAYILAN_ADMIN_PAROLA.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    baglanti.execute(
        sa.text(
            "INSERT INTO users (username, password_hash, is_admin, created_at) "
            "VALUES (:username, :password_hash, 1, :created_at)"
        ),
        {
            "username": VARSAYILAN_ADMIN_KULLANICI_ADI,
            "password_hash": admin_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    admin_id = baglanti.execute(
        sa.text("SELECT id FROM users WHERE username = :username"),
        {"username": VARSAYILAN_ADMIN_KULLANICI_ADI},
    ).scalar_one()

    for tablo in ("tasks", "calendar_events", "plan_kayitlari", "profil"):
        op.add_column(tablo, sa.Column('user_id', sa.Integer(), nullable=True))
        baglanti.execute(sa.text(f"UPDATE {tablo} SET user_id = :admin_id"), {"admin_id": admin_id})

    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_tasks_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # calendar_events'teki eski `UNIQUE (google_id)` kısıtı isimsiz (SQLite otomatik
    # isimlendirmiş) — Alembic batch_alter_table ile isimsiz kısıtı hedefleyip
    # kaldıramıyoruz, bu yüzden tabloyu elle (user_id, google_id) bileşik
    # benzersizliğiyle yeniden oluşturup veriyi taşıyoruz.
    baglanti.execute(sa.text("""
        CREATE TABLE calendar_events_new (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            google_id VARCHAR(300) NOT NULL,
            title VARCHAR(300) NOT NULL,
            description VARCHAR(2000) NOT NULL,
            start VARCHAR(50) NOT NULL,
            "end" VARCHAR(50) NOT NULL,
            updated VARCHAR(50) NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE (user_id, google_id)
        )
    """))
    baglanti.execute(sa.text(
        'INSERT INTO calendar_events_new (id, user_id, google_id, title, description, start, "end", updated) '
        'SELECT id, user_id, google_id, title, description, start, "end", updated FROM calendar_events'
    ))
    baglanti.execute(sa.text("DROP TABLE calendar_events"))
    baglanti.execute(sa.text("ALTER TABLE calendar_events_new RENAME TO calendar_events"))

    with op.batch_alter_table('plan_kayitlari') as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_plan_kayitlari_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('profil') as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_profil_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_unique_constraint('uq_profil_user_id', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('profil') as batch_op:
        batch_op.drop_constraint('uq_profil_user_id', type_='unique')
        batch_op.drop_constraint('fk_profil_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('plan_kayitlari') as batch_op:
        batch_op.drop_constraint('fk_plan_kayitlari_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')

    baglanti = op.get_bind()
    baglanti.execute(sa.text("""
        CREATE TABLE calendar_events_old (
            id INTEGER NOT NULL PRIMARY KEY,
            google_id VARCHAR(300) NOT NULL,
            title VARCHAR(300) NOT NULL,
            description VARCHAR(2000) NOT NULL,
            start VARCHAR(50) NOT NULL,
            "end" VARCHAR(50) NOT NULL,
            updated VARCHAR(50) NOT NULL,
            UNIQUE (google_id)
        )
    """))
    baglanti.execute(sa.text(
        'INSERT INTO calendar_events_old (id, google_id, title, description, start, "end", updated) '
        'SELECT id, google_id, title, description, start, "end", updated FROM calendar_events'
    ))
    baglanti.execute(sa.text("DROP TABLE calendar_events"))
    baglanti.execute(sa.text("ALTER TABLE calendar_events_old RENAME TO calendar_events"))

    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_constraint('fk_tasks_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')

    op.drop_table('users')
