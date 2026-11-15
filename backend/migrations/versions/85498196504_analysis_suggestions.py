"""Persist analysis conduct flags, accepted attack hints and honest usage accounting."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "85498196504"
down_revision = "85498196503"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "message_analyses",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("debate_chats", sa.Column("attack_hint", sa.Text(), nullable=True))
    op.add_column(
        "message_analyses",
        sa.Column(
            "conduct_flags", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "llm_usage_events",
        sa.Column(
            "usage_reported", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column(
        "llm_usage_events",
        "estimated_cost",
        existing_type=sa.Numeric(18, 8),
        nullable=True,
    )


def downgrade():
    op.drop_column("message_analyses", "started_at")
    op.execute(
        "UPDATE llm_usage_events SET estimated_cost = 0 WHERE estimated_cost IS NULL"
    )
    op.alter_column(
        "llm_usage_events",
        "estimated_cost",
        existing_type=sa.Numeric(18, 8),
        nullable=False,
    )
    op.drop_column("llm_usage_events", "usage_reported")
    op.drop_column("message_analyses", "conduct_flags")
    op.drop_column("debate_chats", "attack_hint")
