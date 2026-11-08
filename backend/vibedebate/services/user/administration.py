from dataclasses import dataclass
from uuid import UUID
from vibedebate.models.user import User
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.services.user.keycloak import KeycloakUserClient
from vibedebate.models.enums import UserStatus, AdminAction
from vibedebate.repositories.user import UserRepository
from vibedebate.repositories.audit import AuditRepository
from vibedebate.services.user.exceptions import (
    UserNotFoundError,
    SelfBlockingError,
    SelfUnblockingError,
    DeletedUserStatusChangeError,
)


@dataclass
class UserAdministrationService:
    user_repository: UserRepository
    audit_repository: AuditRepository
    keycloak_client: KeycloakUserClient

    async def ban_user(
        self, current_user: CurrentUser, user_id: UUID, reason: str
    ) -> None:
        user = await self._get_user_for_status_change(user_id)
        if current_user.subject == user.keycloak_sub:
            raise SelfBlockingError()
        admin = await self.user_repository.get_or_create_user(
            current_user.subject, current_user.display_name
        )
        await self.keycloak_client.set_user_blocked(user.keycloak_sub, blocked=True)
        await self.user_repository.update_user_status(user, UserStatus.BANNED)
        await self.audit_repository.create_audit_entry(
            admin.id, user_id, AdminAction.BAN_USER, reason
        )

    async def unban_user(
        self, current_user: CurrentUser, user_id: UUID, reason: str
    ) -> None:
        user = await self._get_user_for_status_change(user_id)
        if current_user.subject == user.keycloak_sub:
            raise SelfUnblockingError()
        admin = await self.user_repository.get_or_create_user(
            current_user.subject, current_user.display_name
        )
        await self.keycloak_client.set_user_blocked(user.keycloak_sub, blocked=False)
        await self.user_repository.update_user_status(user, UserStatus.ACTIVE)
        await self.audit_repository.create_audit_entry(
            admin.id, user_id, AdminAction.UNBAN_USER, reason
        )

    async def _get_user_for_status_change(self, user_id: UUID) -> User:
        user = await self.user_repository.get_user_by_id(user_id, for_update=True)
        if user is None:
            raise UserNotFoundError()
        if user.status == UserStatus.DELETED:
            raise DeletedUserStatusChangeError()
        return user
