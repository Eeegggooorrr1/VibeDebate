from uuid import UUID
from vibedebate.core.auth.roles import Role
from vibedebate.models.enums import UserStatus
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_name: str | None
    status: UserStatus
    level: str | None
    goals: list[str]
    preferred_difficulty: int | None
    onboarding_completed: bool
    interests: list[UUID]
    roles: list[Role]
