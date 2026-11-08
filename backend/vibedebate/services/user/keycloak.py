import asyncio
import time
from urllib.parse import quote
import httpx
from vibedebate.core.config import KeycloakAdminSettings
from vibedebate.services.user.exceptions import (
    UserProviderUnavailableError,
    UserNotFoundError,
)


class KeycloakUserClient:
    def __init__(self, settings: KeycloakAdminSettings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client
        self.access_token = ""
        self.expires_at = 0.0
        self.lock = asyncio.Lock()

    async def _get_access_token(self) -> str:
        async with self.lock:
            if time.monotonic() < self.expires_at:
                return self.access_token
            response = await self.client.post(
                self.settings.keycloak_admin_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.keycloak_service_client_id,
                    "client_secret": self.settings.keycloak_service_client_secret,
                },
            )
            response.raise_for_status()
            payload = response.json()
            self.access_token = payload["access_token"]
            self.expires_at = time.monotonic() + max(0, int(payload["expires_in"]) - 30)
            return self.access_token

    async def set_user_blocked(self, subject: str, *, blocked: bool) -> None:
        try:
            headers = {"Authorization": "Bearer " + await self._get_access_token()}
            url = (
                self.settings.keycloak_admin_api_url.rstrip("/")
                + "/users/"
                + quote(subject, safe="")
            )
            response = await self.client.get(url, headers=headers)
            if response.status_code == 404:
                raise UserNotFoundError("User not found in Keycloak")
            response.raise_for_status()
            user = response.json()
            attributes = user.get("attributes") or {}
            attributes["blocked"] = ["true" if blocked else "false"]
            # Preserve attributes not owned by the block operation.
            response = await self.client.put(
                url, headers=headers, json={**user, "attributes": attributes}
            )
            response.raise_for_status()
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise UserProviderUnavailableError(
                "Could not update the user block flag"
            ) from exc
