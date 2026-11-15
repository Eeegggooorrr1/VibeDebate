"""Snapshot topic titles and enforce one unfinished response per chat."""

from alembic import op
import sqlalchemy as sa

revision = "85498196503"
down_revision = "85498196502"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("debates", sa.Column("topic_title", sa.Text(), nullable=True))
    op.execute(
        "UPDATE debates SET topic_title = COALESCE(custom_topic, (SELECT title FROM topics WHERE topics.id = debates.topic_id))"
    )
    op.alter_column("debates", "topic_title", nullable=False)
    op.create_index(
        "uq_chat_messages_unfinished_turn",
        "chat_messages",
        ["chat_id"],
        unique=True,
        postgresql_where=sa.text(
            "role = 'assistant' AND generation_status IN ('pending','generating')"
        ),
    )


def downgrade():
    op.drop_index("uq_chat_messages_unfinished_turn", table_name="chat_messages")
    op.drop_column("debates", "topic_title")
