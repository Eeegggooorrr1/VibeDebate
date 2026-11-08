from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from vibedebate.models.user import User, UserInterest
from vibedebate.models.enums import UserStatus
from vibedebate.schemas.requests.user import ProfileUpdate


@dataclass
class UserRepository:
    session: AsyncSession

    async def get_or_create_user(self, subject: str, display_name: str | None) -> User:
        existing = await self.session.scalar(
            select(User).where(User.keycloak_sub == subject)
        )
        if existing is not None:
            return existing
        await self.session.execute(
            insert(User)
            .values(keycloak_sub=subject, display_name=display_name)
            .on_conflict_do_nothing(index_elements=[User.keycloak_sub])
        )
        return (
            await self.session.scalars(select(User).where(User.keycloak_sub == subject))
        ).one()

    async def get_user_by_id(
        self, user_id: UUID, *, for_update: bool = False
    ) -> User | None:
        # Refresh cached ORM state after acquiring the row lock.
        return await self.session.get(
            User, user_id, with_for_update=for_update, populate_existing=for_update
        )

    async def list_user_interest_ids(self, user_id: UUID) -> list[UUID]:
        return list(
            await self.session.scalars(
                select(UserInterest.topic_category_id).where(
                    UserInterest.user_id == user_id
                )
            )
        )

    async def update_user_profile(self, user: User, profile: ProfileUpdate) -> None:
        user.display_name = profile.display_name
        user.level = profile.level
        user.goals = profile.goals
        user.preferred_difficulty = profile.preferred_difficulty
        user.onboarding_completed = True
        await self.session.execute(
            delete(UserInterest).where(UserInterest.user_id == user.id)
        )
        self.session.add_all(
            [
                UserInterest(user_id=user.id, topic_category_id=category_id)
                for category_id in profile.interests
            ]
        )
        await self.session.flush()

    async def update_user_status(self, user: User, status: UserStatus) -> None:
        user.status = status
        await self.session.flush()
