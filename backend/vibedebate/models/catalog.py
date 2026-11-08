from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from vibedebate.models.base import Base, Entity


class TopicCategory(Entity, Base):
    __tablename__ = "topic_categories"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_self_parent"),
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("topic_categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class Topic(Entity, Base):
    __tablename__ = "topics"
    __table_args__ = (
        CheckConstraint("topic_type IN ('question','thesis','statement')", name="type"),
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("topic_categories.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    topic_type: Mapped[str] = mapped_column(String(16))
    default_positions: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    tags: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    is_available_in_basic_mode: Mapped[bool] = mapped_column(
        default=True, server_default="true"
    )


class OpponentPersona(Entity, Base):
    __tablename__ = "opponent_personas"
    __table_args__ = (
        CheckConstraint(
            "available_difficulties <@ '[1,2,3]'::jsonb AND jsonb_array_length(available_difficulties) > 0",
            name="difficulties",
        ),
    )
    key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    base_prompt_config: Mapped[dict] = mapped_column(JSONB)
    available_difficulties: Mapped[list] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class LearningAsset(Entity, Base):
    __tablename__ = "learning_assets"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 3", name="difficulty"),
        CheckConstraint(
            "asset_type IN ('explanation','quiz','rewrite','classification','guided_practice')",
            name="type",
        ),
    )
    skill_key: Mapped[str] = mapped_column(String(100), index=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[dict] = mapped_column(JSONB)
    difficulty: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    details: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
