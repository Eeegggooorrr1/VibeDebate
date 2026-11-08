import asyncio
import httpx
import pytest
from fastapi import FastAPI
from dishka import Provider, Scope, provide, make_async_container
from dishka.integrations.fastapi import DishkaRoute, FastapiProvider, setup_dishka
from vibedebate.core.auth.annotations import AuthenticatedUser, AdminUser
from vibedebate.core.auth.guards import RequireUser
from vibedebate.core.auth.roles import Role
from vibedebate.core.di.container import AuthenticationProvider
from vibedebate.core.exceptions import AppError, UnauthorizedError
from vibedebate.handlers.errors import app_error_handler
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.services.user.tokens import TokenVerifier
from vibedebate.services.user.exceptions import UserBlockedError


@pytest.mark.parametrize(
    "roles,blocked,user_status,admin_status",
    [
        ([], False, 200, 403),
        ([Role.USER], False, 200, 403),
        ([Role.ADMIN], False, 200, 200),
        ([Role.ADMIN], True, 403, 403),
    ],
)
def test_user_dependencies_need_no_database(roles, blocked, user_status, admin_status):
    current_user = CurrentUser("subject", "Test", frozenset(roles), blocked)

    class FakeVerifier:
        async def verify_access_token(self, token):
            return current_user

    class Tokens(Provider):
        @provide(scope=Scope.APP)
        def verifier(self) -> TokenVerifier:
            return FakeVerifier()

    async def run():
        # The real authentication provider resolves without a session or repository.
        container = make_async_container(
            Tokens(), AuthenticationProvider(), FastapiProvider()
        )
        app = FastAPI()
        app.router.route_class = DishkaRoute
        app.add_exception_handler(AppError, app_error_handler)
        setup_dishka(container, app)
        calls = []

        @app.get("/user")
        async def user_route(user: AuthenticatedUser):
            calls.append("user")
            return {"subject": user.subject}

        @app.get("/admin")
        async def admin_route(user: AdminUser):
            calls.append("admin")
            return {"subject": user.subject}

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (await client.get("/user")).status_code == 401
                headers = {"Authorization": "Bearer test"}
                assert (
                    await client.get("/user", headers=headers)
                ).status_code == user_status
                assert (
                    await client.get("/admin", headers=headers)
                ).status_code == admin_status
            assert calls == (["user"] if user_status == 200 else []) + (
                ["admin"] if admin_status == 200 else []
            )
            assert app.openapi()["paths"]["/user"]["get"].get("parameters", []) == []
        finally:
            await container.close()

    asyncio.run(run())


def test_require_user_rejects_string_roles():
    with pytest.raises(ValueError):
        RequireUser("admin")


def test_error_overrides_do_not_mutate_class_defaults():
    error = UserBlockedError(
        "Custom explanation",
        code="custom_code",
        status_code=409,
        extra={"reason": "test"},
    )
    assert str(error) == "Custom explanation"
    assert error.code == "custom_code"
    assert error.status_code == 409
    assert error.extra == {"reason": "test"}
    original = UserBlockedError()
    assert original.code == "user_blocked"
    assert original.status_code == 403
    assert original.extra is None


@pytest.mark.parametrize(
    "error",
    [
        AppError(),
        UnauthorizedError(),
        UserBlockedError("Blocked", extra={"field": "status"}),
    ],
)
def test_error_handler_serializes_declared_error(error):
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/error")
    async def fail():
        raise error

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/error")
        assert response.status_code == error.status_code
        expected = {"code": error.code, "message": error.message}
        if error.extra is not None:
            expected["extra"] = error.extra
        assert response.json() == {"error": expected}
        assert response.headers.get("WWW-Authenticate") == (
            "Bearer" if error.status_code == 401 else None
        )

    asyncio.run(run())
