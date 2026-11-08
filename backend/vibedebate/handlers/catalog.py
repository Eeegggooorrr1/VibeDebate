from fastapi import APIRouter
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from vibedebate.core.auth.annotations import AuthenticatedUser
from vibedebate.schemas.responses.catalog import CategoryResponse
from vibedebate.services.catalog.categories import CategoryService

router = APIRouter(prefix="/api/v1/topics", route_class=DishkaRoute, tags=["catalog"])


@router.get("/categories", response_model=list[CategoryResponse])
async def list_active_categories(
    user: AuthenticatedUser,
    service: FromDishka[CategoryService]
) -> list[CategoryResponse]:
    return await service.list_active_categories()
