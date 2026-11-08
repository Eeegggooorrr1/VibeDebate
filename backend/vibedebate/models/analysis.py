from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    DateTime,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from vibedebate.models.base import Base, Entity


class MessageAnalysis(Entity, Base):
    __tablename__ = "message_analyses"
    __table_args__ = (
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="score"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        CheckConstraint(
            "is_substantive IS TRUE OR overall_score IS NULL", name="substantive_score"
        ),
        CheckConstraint(
            "analysis_status IN ('pending','running','completed','failed')",
            name="status",
        ),
    )
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"), unique=True
    )
    is_substantive: Mapped[bool | None]
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    dimensions: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    strengths: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    next_step: Mapped[str | None] = mapped_column(Text)
    analysis_status: Mapped[str] = mapped_column(String(16))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisIssue(Entity, Base):
    __tablename__ = "analysis_issues"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        CheckConstraint("severity IN ('low','medium','high')", name="severity"),
    )
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("message_analyses.id", ondelete="CASCADE"), index=True
    )
    issue_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    evidence_quote: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    improvement: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))


class LLMUsageEvent(Entity, Base):
    __tablename__ = "llm_usage_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_id", "debate_id", "user_id"],
            ["debate_chats.id", "debate_chats.debate_id", "debate_chats.user_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["message_id", "chat_id"],
            ["chat_messages.id", "chat_messages.chat_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND cached_input_tokens >= 0 AND reasoning_tokens >= 0 AND latency_ms >= 0 AND estimated_cost >= 0",
            name="nonnegative",
        ),
        CheckConstraint(
            "chat_id IS NULL OR debate_id IS NOT NULL", name="chat_context"
        ),
        CheckConstraint(
            "message_id IS NULL OR chat_id IS NOT NULL", name="message_context"
        ),
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    debate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("debates.id", ondelete="CASCADE")
    )
    chat_id: Mapped[UUID | None]
    message_id: Mapped[UUID | None]
    operation_type: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    cached_input_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    reasoning_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    currency: Mapped[str] = mapped_column(String(3))
    is_estimated: Mapped[bool]
    latency_ms: Mapped[int]
    status: Mapped[str] = mapped_column(String(32))
