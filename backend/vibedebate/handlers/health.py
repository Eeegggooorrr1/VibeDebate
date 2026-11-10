import asyncio

import httpx
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from vibedebate.core.config import UserSettings

router = APIRouter(route_class=DishkaRoute, tags=["health"])


@router.get("/health/ready", include_in_schema=False)
async def readiness(
    engine: FromDishka[AsyncEngine],
    client: FromDishka[httpx.AsyncClient],
    settings: FromDishka[UserSettings],
) -> JSONResponse:
    try:
        async with asyncio.timeout(4):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

            response = await client.get(settings.keycloak_jwks_url, timeout=2)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict) or not payload.get("keys"):
                raise ValueError("No signing keys")
    except (SQLAlchemyError, httpx.HTTPError, TimeoutError, ValueError, OSError):
        return JSONResponse({"status": "not_ready"}, status_code=503)

    return JSONResponse({"status": "ready"})
