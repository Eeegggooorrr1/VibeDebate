"""Track the source of chat mastery."""

from alembic import op
import sqlalchemy as sa

revision = "85498196507"
down_revision = "85498196506"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "debate_chats", sa.Column("mastery_source", sa.String(32), nullable=True)
    )
    op.execute(
        "UPDATE debate_chats SET mastery_source='statistics' WHERE mastered_at IS NOT NULL"
    )


def downgrade():
    op.drop_column("debate_chats", "mastery_source")
