from uuid import UUID
from vibedebate.models.enums import UserStatus
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from vibedebate.models.base import Base, Entity, Updated


class User(Entity, Updated, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('active','banned','deleted')", name="status"),
        CheckConstraint(
            "level IS NULL OR level IN ('beginner','intermediate','advanced')",
            name="level",
        ),
        CheckConstraint(
            "preferred_difficulty IS NULL OR preferred_difficulty BETWEEN 1 AND 3",
            name="difficulty",
        ),
    )
    keycloak_sub: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(16), default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE.value
    )
    level: Mapped[str | None] = mapped_column(String(16))
    goals: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    preferred_difficulty: Mapped[int | None]
    onboarding_completed: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )


class UserInterest(Base):
    __tablename__ = "user_interests"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topic_category_id: Mapped[UUID] = mapped_column(
        ForeignKey("topic_categories.id", ondelete="CASCADE"), primary_key=True
    )


class AdminAuditLog(Entity, Base):
    __tablename__ = "admin_audit_log"
    admin_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[UUID]
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
