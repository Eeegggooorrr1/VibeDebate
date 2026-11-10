from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=255)
    level: Literal["beginner", "intermediate", "advanced"]
    interests: list[UUID] = Field(min_length=1, max_length=20)
    goals: list[str] = Field(min_length=1, max_length=10)
    preferred_difficulty: Literal[1, 2, 3] | None = None

    @field_validator("goals")
    @classmethod
    def validate_goals(
        cls,
        values: list[str],
    ) -> list[str]:
        if any(not 1 <= len(v) <= 100 for v in values) or len(set(values)) != len(
            values
        ):
            raise ValueError("Goals must be unique and contain 1 to 100 characters")

        return values

    @field_validator("interests")
    @classmethod
    def unique_interests(
        cls,
        values: list[UUID],
    ) -> list[UUID]:
        if len(set(values)) != len(values):
            raise ValueError("Interests must be unique")

        return values


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=1000)
