import os
from alembic import command
from alembic.config import Config


import asyncio
import time
from uuid import uuid4
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk
from dishka import Provider, Scope, provide, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy import select, func
from vibedebate.core.config import DatabaseSettings, UserSettings
from vibedebate.core.di.container import (
    InfrastructureProvider,
    AuthenticationProvider,
)
from vibedebate.services.user.exceptions import (
    InvalidAccessTokenError,
    UserProviderUnavailableError,
)
from vibedebate.main import create_app
from vibedebate.models import AdminAuditLog
from vibedebate.services.user.tokens import TokenVerifier


@pytest.fixture(scope="module")
def migrate_test_database():
    original = os.environ.get("POSTGRES_DB")
    os.environ["POSTGRES_DB"] = "vibedebate_test"
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if original is None:
            os.environ.pop("POSTGRES_DB", None)
        else:
            os.environ["POSTGRES_DB"] = original


PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = PRIVATE.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
PUBLIC = jwk.construct(
    PRIVATE.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ),
    algorithm="RS256",
).to_dict()
PUBLIC.update(kid="test", use="sig", alg="RS256")
SETTINGS = UserSettings(
    keycloak_issuer="https://user.test/realms/test",
    keycloak_jwks_url="https://user.test/certs",
    keycloak_audience="api",
    keycloak_client_id="web",
    _env_file=None,
)


def token(subject="alice", roles=None, **changes):
    claims = {
        "sub": subject,
        "iss": SETTINGS.keycloak_issuer,
        "aud": "api",
        "iat": int(time.time()),
        "exp": int(time.time()) + 120,
        "typ": "Bearer",
        "resource_access": {"api": {"roles": roles if roles is not None else ["user"]}},
    }
    claims.update(changes)
    return jwt.encode(claims, PEM, algorithm="RS256", headers={"kid": "test"})


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": 1},
        {"iss": "wrong"},
        {"aud": "wrong"},
        {"typ": "ID"},
        {"sub": ""},
        {"blocked": "false"},
        {"blocked": 1},
        {"blocked": None},
    ],
)
def test_rejects_invalid_claims(changes):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"keys": [PUBLIC]})
            )
        ) as client:
            with pytest.raises(InvalidAccessTokenError):
                await TokenVerifier(SETTINGS, client).verify_access_token(
                    token(**changes)
                )

    asyncio.run(run())


def test_jwks_outage_is_not_an_invalid_password():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(503))
        ) as client:
            with pytest.raises(UserProviderUnavailableError):
                await TokenVerifier(SETTINGS, client).verify_access_token(token())

    asyncio.run(run())


def test_api_user_rbac_and_audit(migrate_test_database):
    async def run():
        class TestConfig(Provider):
            @provide(scope=Scope.APP)
            def database(self) -> DatabaseSettings:
                return DatabaseSettings(
                    postgres_host="127.0.0.1",
                    postgres_port=15433,
                    postgres_db="vibedebate_test",
                    postgres_user="vibedebate",
                    postgres_password="vibedebate-local",
                    _env_file=None,
                )

            @provide(scope=Scope.APP)
            def user(self) -> UserSettings:
                return SETTINGS

            @provide(scope=Scope.APP, override=True)
            def verifier(self) -> TokenVerifier:
                verifier = TokenVerifier(SETTINGS, httpx.AsyncClient())
                verifier.keys = [PUBLIC]
                verifier.expires_at = time.monotonic() + 1000
                return verifier

        from vibedebate.core.di.container import ApplicationProvider
        from vibedebate.core.config import SeedSettings
        from vibedebate.services.user.keycloak import KeycloakUserClient

        class FakeKeycloakUserClient(KeycloakUserClient):
            def __init__(self):
                self.blocked_users = {}
                self.fail = False

            async def set_user_blocked(self, subject: str, *, blocked: bool) -> None:
                if self.fail:
                    from vibedebate.services.user.exceptions import (
                        UserProviderUnavailableError,
                    )

                    raise UserProviderUnavailableError()
                self.blocked_users[subject] = blocked

        class TestSeedConfig(Provider):
            @provide(scope=Scope.APP, override=True)
            def keycloak_client(self) -> KeycloakUserClient:
                return FakeKeycloakUserClient()

            @provide(scope=Scope.APP)
            def seed_settings(self) -> SeedSettings:
                return SeedSettings()

        container = make_async_container(
            InfrastructureProvider(),
            ApplicationProvider(),
            AuthenticationProvider(),
            FastapiProvider(),
            TestConfig(),
            TestSeedConfig(),
        )
        app = create_app(container)
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine = await container.get(AsyncEngine)

        subject = str(uuid4())
        headers = {"Authorization": "Bearer " + token(subject)}
        admin = {"Authorization": "Bearer " + token(str(uuid4()), ["admin"])}
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (await client.get("/api/v1/me")).status_code == 401
                denied = await client.get(
                    "/api/v1/me",
                    headers={"Authorization": "Bearer " + token(str(uuid4()), [])},
                )
                assert denied.status_code == 200
                response = await client.get("/api/v1/me", headers=headers)
                assert response.status_code == 200, response.text
                user = response.json()
                assert not user["onboarding_completed"]
                assert (await client.get("/api/v1/me", headers=headers)).json()[
                    "id"
                ] == user["id"]
                from vibedebate.cli.bootstrap.seed_service import SeedService
                from vibedebate.core.config import SeedSettings
                from sqlalchemy.ext.asyncio import AsyncSession

                async with AsyncSession(engine) as session:
                    async with session.begin():
                        await SeedService(session, SeedSettings()).load_data()
                profile = {
                    "display_name": "Alice",
                    "level": "beginner",
                    "goals": ["logic"],
                    "interests": ["10000000-0000-0000-0000-000000000001"],
                }
                updated = await client.patch(
                    "/api/v1/me/profile", headers=headers, json=profile
                )
                assert updated.status_code == 200, updated.text
                assert updated.json()["onboarding_completed"]
                assert updated.json()["interests"] == profile["interests"]
                profile["interests"] = [str(uuid4())]
                assert (
                    await client.patch(
                        "/api/v1/me/profile", headers=headers, json=profile
                    )
                ).status_code == 422
                assert (await client.get("/api/v1/me", headers=headers)).json()[
                    "interests"
                ] == updated.json()["interests"]
                assert (
                    await client.get("/api/v1/topics/categories", headers=headers)
                ).status_code == 200
                unknown_role = {
                    "Authorization": "Bearer "
                    + token(str(uuid4()), ["unrelated-admin"])
                }
                assert (
                    await client.get("/api/v1/me", headers=unknown_role)
                ).status_code == 200
                assert (
                    app.openapi()["paths"]["/api/v1/me"]["get"].get("parameters", [])
                    == []
                )
                admin_profile = (await client.get("/api/v1/me", headers=admin)).json()
                self_ban = await client.post(
                    "/api/v1/admin/users/" + admin_profile["id"] + "/ban",
                    headers=admin,
                    json={"reason": "test"},
                )
                assert self_ban.status_code == 409
                assert self_ban.json()["error"]["code"] == "self_blocking_forbidden"
                missing_user = await client.post(
                    "/api/v1/admin/users/" + str(uuid4()) + "/ban",
                    headers=admin,
                    json={"reason": "test"},
                )
                assert missing_user.status_code == 404
                assert missing_user.json()["error"]["code"] == "user_not_found"
                path = "/api/v1/admin/users/" + user["id"] + "/ban"
                assert (
                    await client.post(path, headers=headers, json={"reason": "test"})
                ).status_code == 403
                keycloak_client = await container.get(KeycloakUserClient)
                keycloak_client.fail = True
                assert (
                    await client.post(path, headers=admin, json={"reason": "test"})
                ).status_code == 503
                assert (await client.get("/api/v1/me", headers=headers)).json()[
                    "status"
                ] == "active"
                keycloak_client.fail = False
                assert (
                    await client.post(path, headers=admin, json={"reason": "test"})
                ).status_code == 204
                assert (
                    await client.get("/api/v1/me", headers=headers)
                ).status_code == 200
                blocked = await client.get(
                    "/api/v1/me",
                    headers={"Authorization": "Bearer " + token(subject, blocked=True)},
                )
                assert blocked.status_code == 403
                assert blocked.json()["error"]["code"] == "user_blocked"
                assert (
                    await client.post(
                        path.replace("/ban", "/unban"),
                        headers=admin,
                        json={"reason": "test"},
                    )
                ).status_code == 204
                assert (
                    await client.get("/api/v1/me", headers=headers)
                ).status_code == 200
                async with engine.connect() as connection:
                    count = await connection.scalar(
                        select(func.count())
                        .select_from(AdminAuditLog)
                        .where(AdminAuditLog.target_id == user["id"])
                    )
                    assert count == 2
        finally:
            await container.close()

    asyncio.run(run())


def test_generic_seed_lookup_merge_and_rollback(migrate_test_database, tmp_path):
    import json
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from vibedebate.core.db import create_engine, transaction
    from vibedebate.core.config import SeedSettings
    from vibedebate.cli.bootstrap.seed_service import SeedService
    from vibedebate.models import User

    async def run():
        engine = create_engine(
            DatabaseSettings(
                postgres_host="127.0.0.1",
                postgres_port=15433,
                postgres_db="vibedebate_test",
                postgres_user="vibedebate",
                postgres_password="vibedebate-local",
                _env_file=None,
            )
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = SeedSettings(seed_dir=tmp_path, _env_file=None)
        user_id, alternate, merged = uuid4(), uuid4(), uuid4()
        subject = str(uuid4())
        first = tmp_path / "01-users.json"
        second = tmp_path / "02-updates.json"

        def save(path, records):
            path.write_text(json.dumps(records), encoding="utf-8")

        save(
            first,
            [
                {
                    "model": "vibedebate.models.user.User",
                    "id": str(user_id),
                    "lookup": ["keycloak_sub"],
                    "fields": {"keycloak_sub": subject, "display_name": "Initial"},
                }
            ],
        )
        save(
            second,
            [
                {
                    "model": "vibedebate.models.user.User",
                    "id": str(alternate),
                    "lookup": ["keycloak_sub"],
                    "fields": {"keycloak_sub": subject, "display_name": "Updated"},
                },
                {
                    "model": "vibedebate.models.user.User",
                    "id": str(merged),
                    "fields": {"keycloak_sub": str(uuid4()), "display_name": "Merged"},
                },
            ],
        )
        try:
            for _ in range(2):
                async with transaction(factory) as session:
                    await SeedService(session, settings).load_data()
            async with factory() as session:
                user = await session.get(User, user_id)
                assert user.display_name == "Updated"
                assert await session.get(User, alternate) is None
                assert (await session.get(User, merged)).display_name == "Merged"
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(User)
                        .where(User.keycloak_sub == subject)
                    )
                    == 1
                )

            save(
                first,
                [
                    {
                        "model": "vibedebate.models.user.User",
                        "id": str(user_id),
                        "lookup": ["keycloak_sub"],
                        "fields": {"keycloak_sub": subject, "display_name": "Rollback"},
                    }
                ],
            )
            save(
                second,
                [
                    {
                        "model": "vibedebate.models.user.User",
                        "lookup": ["keycloak_sub"],
                        "fields": {"display_name": "Missing lookup field"},
                    }
                ],
            )
            with pytest.raises(ValueError, match="Lookup field is missing"):
                async with transaction(factory) as session:
                    await SeedService(session, settings).load_data()
            async with factory() as session:
                assert (await session.get(User, user_id)).display_name == "Updated"
        finally:
            await engine.dispose()

    asyncio.run(run())
