from dishka.integrations.fastapi import FromDishka, inject
from vibedebate.core.auth.roles import Role
from vibedebate.core.exceptions import ForbiddenError
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.services.user.exceptions import UserBlockedError


class RequireUser:
    def __init__(self, *roles: Role) -> None:
        if any(not isinstance(role, Role) for role in roles):
            raise ValueError("RequireUser expects Role members")
        self.allowed_roles = frozenset(roles)

    @inject
    async def __call__(self, user: FromDishka[CurrentUser]) -> CurrentUser:
        if user.blocked:
            raise UserBlockedError()
        if self.allowed_roles and self.allowed_roles.isdisjoint(user.roles):
            raise ForbiddenError(
                "Insufficient role",
                extra={
                    "required_roles": sorted(self.allowed_roles),
                    "user_roles": sorted(user.roles),
                },
            )
        return user
