from dataclasses import dataclass
from vibedebate.repositories.user import UserRepository
from vibedebate.repositories.catalog import CategoryRepository
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.schemas.requests.user import ProfileUpdate
from vibedebate.schemas.responses.user import UserResponse
from vibedebate.services.user.exceptions import (
    InvalidProfileInterestsError,
    UserDeletedError,
)
from vibedebate.models.enums import UserStatus
from vibedebate.models.user import User


@dataclass
class UserService:
    user_repository: UserRepository
    category_repository: CategoryRepository

    async def get_profile(
        self,
        current_user: CurrentUser,
    ) -> UserResponse:
        user = await self.user_repository.get_or_create_user(
            current_user.subject, current_user.display_name
        )

        return await self._build_profile(user, current_user)

    async def update_profile(
        self,
        current_user: CurrentUser,
        profile: ProfileUpdate,
    ) -> UserResponse:
        if not await self.category_repository.are_categories_active(profile.interests):
            raise InvalidProfileInterestsError()

        user = await self.user_repository.get_or_create_user(
            current_user.subject, current_user.display_name
        )

        user = await self.user_repository.get_user_by_id(user.id, for_update=True)

        if user.status == UserStatus.DELETED:
            raise UserDeletedError()

        await self.user_repository.update_user_profile(user, profile)

        return await self._build_profile(user, current_user)

    async def _build_profile(
        self,
        user: User,
        current_user: CurrentUser,
    ) -> UserResponse:
        if user.status == UserStatus.DELETED:
            raise UserDeletedError()

        return UserResponse(
            id=user.id,
            display_name=user.display_name,
            status=user.status,
            level=user.level,
            goals=user.goals,
            preferred_difficulty=user.preferred_difficulty,
            onboarding_completed=user.onboarding_completed,
            interests=await self.user_repository.list_user_interest_ids(user.id),
            roles=sorted(current_user.roles),
        )
