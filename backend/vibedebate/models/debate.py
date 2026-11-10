from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    String,
    Text,
    DateTime,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from vibedebate.models.base import Base, Entity, Updated


class Debate(Entity, Updated, Base):
    __tablename__ = "debates"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        CheckConstraint("mode IN ('basic','advanced')", name="mode"),
        CheckConstraint("status IN ('active','completed','archived')", name="status"),
        CheckConstraint(
            "(topic_id IS NOT NULL) <> (custom_topic IS NOT NULL)", name="one_topic"
        ),
        CheckConstraint(
            "mode <> 'basic' OR topic_id IS NOT NULL", name="basic_catalog"
        ),
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(16))
    topic_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT")
    )
    custom_topic: Mapped[str | None] = mapped_column(Text)
    topic_title: Mapped[str] = mapped_column(Text)
    user_position: Mapped[str] = mapped_column(Text)
    opponent_position: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DebateChat(Entity, Updated, Base):
    __tablename__ = "debate_chats"
    __table_args__ = (
        CheckConstraint("user_role IN ('attacker','defender')", name="user_role"),
        ForeignKeyConstraint(
            ["debate_id", "user_id"],
            ["debates.id", "debates.user_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "debate_id", "user_id"),
        CheckConstraint("side IN ('attack','defense')", name="side"),
        CheckConstraint("difficulty BETWEEN 1 AND 3", name="difficulty"),
        CheckConstraint(
            "status IN ('new','active','mastery_suggested','completed','closed','archived')",
            name="status",
        ),
    )
    debate_id: Mapped[UUID] = mapped_column(index=True)
    user_id: Mapped[UUID] = mapped_column(index=True)
    side: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    attack_hint: Mapped[str | None] = mapped_column(Text)
    seed_claim: Mapped[str] = mapped_column(Text)
    user_role: Mapped[str] = mapped_column(String(100))
    opponent_persona_id: Mapped[UUID] = mapped_column(
        ForeignKey("opponent_personas.id", ondelete="RESTRICT")
    )
    difficulty: Mapped[int]
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )
    local_summary: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(Entity, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index(
            "uq_chat_messages_unfinished_turn",
            "chat_id",
            unique=True,
            postgresql_where=text(
                "role = 'assistant' AND generation_status IN ('pending','generating')"
            ),
        ),
        UniqueConstraint("chat_id", "sequence_no"),
        UniqueConstraint("chat_id", "client_request_id"),
        UniqueConstraint("id", "chat_id"),
        CheckConstraint("sequence_no > 0", name="sequence"),
        CheckConstraint("role IN ('user','assistant','system')", name="role"),
        CheckConstraint(
            "generation_status IN ('pending','generating','completed','failed')",
            name="generation_status",
        ),
    )
    chat_id: Mapped[UUID] = mapped_column(
        ForeignKey("debate_chats.id", ondelete="CASCADE"), index=True
    )
    sequence_no: Mapped[int]
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    is_substantive: Mapped[bool | None]
    generation_status: Mapped[str] = mapped_column(String(16))
    client_request_id: Mapped[str | None] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
