"""Align message uniqueness names with their columns."""

from alembic import op

revision = "85498196501"
down_revision = "85498196500d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE chat_messages RENAME CONSTRAINT uq_chat_messages_chat_id_sequence_no TO uq_chat_messages_swap"
    )
    op.execute(
        "ALTER TABLE chat_messages RENAME CONSTRAINT uq_chat_messages_chat_id_client_request_id TO uq_chat_messages_chat_id_sequence_no"
    )
    op.execute(
        "ALTER TABLE chat_messages RENAME CONSTRAINT uq_chat_messages_swap TO uq_chat_messages_chat_id_client_request_id"
    )


def downgrade():
    upgrade()
