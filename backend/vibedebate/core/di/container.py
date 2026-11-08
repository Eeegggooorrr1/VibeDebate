from collections.abc import AsyncIterator
import httpx
from dishka import Provider, Scope, provide, make_async_container, AsyncContainer
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.requests import Request
from vibedebate.core.config import (
    DatabaseSettings,
    UserSettings,
    SeedSettings,
    create_database_settings,
    create_user_settings,
    create_seed_settings,
    KeycloakAdminSettings,
    create_keycloak_admin_settings,
)
from vibedebate.core.db import create_engine, transaction
from vibedebate.services.user.exceptions import InvalidAccessTokenError
from vibedebate.repositories.user import UserRepository
from vibedebate.repositories.catalog import CategoryRepository
from vibedebate.repositories.audit import AuditRepository
from vibedebate.services.user.tokens import TokenVerifier
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.services.user.keycloak import KeycloakUserClient
from vibedebate.services.user.profile import UserService
from vibedebate.services.user.administration import UserAdministrationService
from vibedebate.services.catalog.categories import CategoryService
from vibedebate.cli.bootstrap.seed_service import SeedService


class ConfigProvider(Provider):
    database = provide(staticmethod(create_database_settings), scope=Scope.APP)
    user = provide(staticmethod(create_user_settings), scope=Scope.APP)
    keycloak_admin = provide(
        staticmethod(create_keycloak_admin_settings), scope=Scope.APP
    )
    seed = provide(staticmethod(create_seed_settings), scope=Scope.APP)


class InfrastructureProvider(Provider):
    @provide(scope=Scope.APP)
    async def engine(self, settings: DatabaseSettings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings)
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide(scope=Scope.APP)
    def sessions(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self, factory: async_sessionmaker[AsyncSession]
    ) -> AsyncIterator[AsyncSession]:
        async with transaction(factory) as session:
            yield session

    @provide(scope=Scope.APP)
    async def http(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            yield client


class ApplicationProvider(Provider):
    verifier = provide(TokenVerifier, scope=Scope.APP)
    keycloak_client = provide(KeycloakUserClient, scope=Scope.APP)
    user_repository = provide(UserRepository, scope=Scope.REQUEST)
    category_repository = provide(CategoryRepository, scope=Scope.REQUEST)
    audit_repository = provide(AuditRepository, scope=Scope.REQUEST)
    profile_service = provide(UserService, scope=Scope.REQUEST)
    administration_service = provide(UserAdministrationService, scope=Scope.REQUEST)
    category_service = provide(CategoryService, scope=Scope.REQUEST)
    seed_service = provide(SeedService, scope=Scope.REQUEST)


class AuthenticationProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def get_current_user(
        self, request: Request, verifier: TokenVerifier
    ) -> CurrentUser:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 16384:
            raise InvalidAccessTokenError()
        return await verifier.verify_access_token(token)


def build_container() -> AsyncContainer:
    return make_async_container(
        ConfigProvider(),
        InfrastructureProvider(),
        ApplicationProvider(),
        AuthenticationProvider(),
        FastapiProvider(),
    )
