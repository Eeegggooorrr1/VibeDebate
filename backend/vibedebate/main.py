import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from vibedebate.core.di.container import build_container
from vibedebate.core.exceptions import AppError
from vibedebate.handlers.errors import app_error_handler
from vibedebate.handlers.user import router as user_router
from vibedebate.handlers.catalog import router as catalog_router


def create_app(container: AsyncContainer | None = None) -> FastAPI:
    container = container or build_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        try:
            yield
        finally:
            await container.close()

    app = FastAPI(title="VibeDebate", lifespan=lifespan)
    app.include_router(user_router)
    app.include_router(catalog_router)
    app.add_exception_handler(AppError, app_error_handler)
    setup_dishka(container, app)
    return app
