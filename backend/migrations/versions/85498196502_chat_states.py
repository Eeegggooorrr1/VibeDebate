"""Preserve the complete chat lifecycle and validate user roles."""

from alembic import op

revision = "85498196502"
down_revision = "85498196501"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_debate_chats_status"), "debate_chats", type_="check")
    op.create_check_constraint(
        "status",
        "debate_chats",
        "status IN ('new','active','mastery_suggested','completed','closed','archived')",
    )
    op.create_check_constraint(
        "user_role", "debate_chats", "user_role IN ('attacker','defender')"
    )


def downgrade():
    op.drop_constraint(op.f("ck_debate_chats_user_role"), "debate_chats", type_="check")
    op.drop_constraint(op.f("ck_debate_chats_status"), "debate_chats", type_="check")
    op.create_check_constraint(
        "status", "debate_chats", "status IN ('active','closed','archived')"
    )
