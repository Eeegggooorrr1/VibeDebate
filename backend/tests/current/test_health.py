from contextlib import asynccontextmanager
import httpx
import pytest

from vibedebate.core.config import UserSettings
from vibedebate.handlers.health import readiness


class FakeEngine:
    def __init__(self, unavailable=False):
        self.unavailable = unavailable

    @asynccontextmanager
    async def connect(self):
        if self.unavailable:
            raise ConnectionRefusedError()
        yield self

    async def execute(self, statement):
        assert str(statement) == "SELECT 1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "database_down,keycloak_status,keys,expected",
    [(False, 200, {"keys": [{}]}, 200), (True, 200, {"keys": [{}]}, 503),
     (False, 503, {}, 503), (False, 200, {"keys": []}, 503),
     (False, 200, [], 503)],
)
async def test_readiness_checks_dependencies(database_down, keycloak_status, keys, expected):
    settings = UserSettings(
        keycloak_issuer="http://identity.test/realms/test",
        keycloak_jwks_url="http://identity.test/certs",
        keycloak_audience="api", keycloak_client_id="web", _env_file=None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(keycloak_status, json=keys)
    )) as client:
        response = await readiness(FakeEngine(database_down), client, settings)
    assert response.status_code == expected
    assert response.body == (b'{"status":"ready"}' if expected == 200 else b'{"status":"not_ready"}')
