"""Persist incremental chat progression; initialize existing analysed history once."""

from alembic import op
import sqlalchemy as sa

revision = "85498196505"
down_revision = "85498196504"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("scored_answers", "good_streak", "progress", "progress_sequence"):
        op.add_column(
            "debate_chats",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    op.add_column(
        "debate_chats",
        sa.Column("score_total", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "debate_chats",
        sa.Column("mastered_at", sa.DateTime(timezone=True), nullable=True),
    )
    connection = op.get_bind()
    chats = connection.execute(sa.text("SELECT id FROM debate_chats")).scalars().all()

    for chat_id in chats:
        rows = connection.execute(
            sa.text("""
            SELECT m.sequence_no, a.analysis_status, a.is_substantive, a.overall_score,
                   EXISTS (SELECT 1 FROM analysis_issues i WHERE i.analysis_id = a.id AND i.severity = 'high') AS critical
            FROM chat_messages m LEFT JOIN message_analyses a ON a.message_id = m.id
            WHERE m.chat_id = :id AND m.role = 'user' ORDER BY m.sequence_no
        """),
            {"id": chat_id},
        )
        count, total, streak, sequence, mastered = 0, 0.0, 0, 0, False

        for seq, status, substantive, score, critical in rows:
            if status != "completed":
                break
            sequence = seq
            if not substantive or score is None:
                continue
            count += 1
            total += float(score)
            streak = min(3, streak + 1) if score >= 75 and not critical else 0
            mastered = mastered or (count >= 5 and total / count >= 75 and streak >= 3)

        progress = (
            100
            if mastered
            else (
                min(
                    99,
                    round(
                        50 * min(1, total / count / 75)
                        + 25 * min(1, count / 5)
                        + 25 * streak / 3
                    ),
                )
                if count
                else 0
            )
        )
        connection.execute(
            sa.text(
                """UPDATE debate_chats SET scored_answers=:count, score_total=:total,
            good_streak=:streak, progress_sequence=:seq, progress=:progress,
            mastered_at=CASE WHEN :mastered THEN now() ELSE NULL END WHERE id=:id"""
            ),
            dict(
                id=chat_id,
                count=count,
                total=total,
                streak=streak,
                seq=sequence,
                progress=progress,
                mastered=mastered,
            ),
        )


def downgrade():
    for name in (
        "mastered_at",
        "score_total",
        "scored_answers",
        "good_streak",
        "progress",
        "progress_sequence",
    ):
        op.drop_column("debate_chats", name)
