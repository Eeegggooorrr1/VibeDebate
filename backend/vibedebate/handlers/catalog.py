from fastapi import APIRouter, Query
from typing import Annotated
from uuid import UUID
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from vibedebate.core.auth.annotations import AuthenticatedUser
from vibedebate.schemas.responses.catalog import CategoryResponse
from vibedebate.schemas.responses.catalog import TopicResponse, PersonaResponse
from vibedebate.services.catalog.categories import CategoryService

router = APIRouter(prefix="/api/v1/topics", route_class=DishkaRoute, tags=["catalog"])


@router.get("", response_model=list[TopicResponse])
async def list_topics(
    user: AuthenticatedUser,
    service: FromDishka[CategoryService],
    category_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TopicResponse]:
    return await service.list_topics(category_id, limit, offset)


@router.get("/opponents", response_model=list[PersonaResponse])
async def list_opponents(
    user: AuthenticatedUser,
    service: FromDishka[CategoryService],
) -> list[PersonaResponse]:
    return await service.list_personas()


@router.get("/categories", response_model=list[CategoryResponse])
async def list_active_categories(
    user: AuthenticatedUser,
    service: FromDishka[CategoryService],
) -> list[CategoryResponse]:
    return await service.list_active_categories()
