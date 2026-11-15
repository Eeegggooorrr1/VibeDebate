"""Preserve reply targets and their original text."""

from alembic import op
import sqlalchemy as sa

revision = "85498196506"
down_revision = "85498196505"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "chat_messages", sa.Column("reply_to_message_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "chat_messages", sa.Column("reply_to_content", sa.Text(), nullable=True)
    )
    op.create_index(
        "ix_chat_messages_reply_to_message_id", "chat_messages", ["reply_to_message_id"]
    )
    op.create_foreign_key(
        "fk_chat_messages_reply_same_chat",
        "chat_messages",
        "chat_messages",
        ["reply_to_message_id", "chat_id"],
        ["id", "chat_id"],
    )
    op.create_check_constraint(
        "reply_not_self",
        "chat_messages",
        "reply_to_message_id IS NULL OR reply_to_message_id <> id",
    )


def downgrade():
    op.drop_constraint(op.f("ck_chat_messages_reply_not_self"), "chat_messages", type_="check")
    op.drop_constraint(
        "fk_chat_messages_reply_same_chat", "chat_messages", type_="foreignkey"
    )
    op.drop_index("ix_chat_messages_reply_to_message_id", table_name="chat_messages")
    op.drop_column("chat_messages", "reply_to_content")
    op.drop_column("chat_messages", "reply_to_message_id")
