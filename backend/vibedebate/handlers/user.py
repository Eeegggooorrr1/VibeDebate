from uuid import UUID
from fastapi import APIRouter, Response
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from vibedebate.core.auth.annotations import AuthenticatedUser, AdminUser
from vibedebate.schemas.requests.user import ProfileUpdate, StatusUpdate
from vibedebate.schemas.responses.user import UserResponse
from vibedebate.services.user.profile import UserService
from vibedebate.services.user.administration import UserAdministrationService

router = APIRouter(prefix="/api/v1", route_class=DishkaRoute, tags=["user"])


@router.get("/me", response_model=UserResponse)
async def get_profile(
    user: AuthenticatedUser,
    service: FromDishka[UserService]
) -> UserResponse:
    return await service.get_profile(user)


@router.patch("/me/profile", response_model=UserResponse)
async def update_profile(
    data: ProfileUpdate, user: AuthenticatedUser, service: FromDishka[UserService]
) -> UserResponse:
    return await service.update_profile(user, data)


@router.post("/admin/users/{user_id}/ban", status_code=204)
async def ban_user(
    user_id: UUID,
    data: StatusUpdate,
    user: AdminUser,
    service: FromDishka[UserAdministrationService],
) -> Response:
    await service.ban_user(user, user_id, data.reason)
    return Response(status_code=204)


@router.post("/admin/users/{user_id}/unban", status_code=204)
async def unban_user(
    user_id: UUID,
    data: StatusUpdate,
    user: AdminUser,
    service: FromDishka[UserAdministrationService],
) -> Response:
    await service.unban_user(user, user_id, data.reason)
    return Response(status_code=204)
