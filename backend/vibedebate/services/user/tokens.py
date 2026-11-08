import asyncio
import time
from typing import Any
import httpx
from jose import jwt, JWTError
from vibedebate.core.config import UserSettings
from vibedebate.services.user.exceptions import (
    InvalidAccessTokenError,
    UserProviderUnavailableError,
)
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.core.auth.roles import Role


class TokenVerifier:
    def __init__(self, settings: UserSettings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client
        self.keys: list[dict[str, Any]] = []
        self.expires_at = 0.0
        self.last_fetch = 0.0
        self.lock = asyncio.Lock()

    async def verify_access_token(self, token: str) -> CurrentUser:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise InvalidAccessTokenError()
            async with self.lock:
                now = time.monotonic()
                known = any(k.get("kid") == header["kid"] for k in self.keys)
                # Unknown kids trigger a bounded refresh to support rotation without a fetch per attack.
                if now >= self.expires_at or (
                    not known and now - self.last_fetch >= 10
                ):
                    try:
                        response = await self.client.get(
                            self.settings.keycloak_jwks_url
                        )
                        response.raise_for_status()
                        keys = response.json()["keys"]
                        if not isinstance(keys, list) or not all(
                            isinstance(k, dict) for k in keys
                        ):
                            raise ValueError("Invalid JWKS")
                    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                        raise UserProviderUnavailableError() from exc
                    self.keys = keys
                    self.last_fetch = now
                    self.expires_at = now + self.settings.jwks_ttl_seconds
                key = next(
                    (
                        k
                        for k in self.keys
                        if k.get("kid") == header["kid"]
                        and k.get("kty") == "RSA"
                        and k.get("use", "sig") == "sig"
                        and k.get("alg", "RS256") == "RS256"
                    ),
                    None,
                )
            if key is None:
                raise InvalidAccessTokenError()
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.keycloak_issuer,
                audience=self.settings.keycloak_audience,
                options={
                    "require_exp": True,
                    "require_iat": True,
                    "require_sub": True,
                    "require_aud": True,
                    "require_iss": True,
                },
            )
            if (
                claims.get("typ") != "Bearer"
                or not isinstance(claims["sub"], str)
                or not 1 <= len(claims["sub"]) <= 255
            ):
                raise InvalidAccessTokenError()
            roles = (
                claims.get("resource_access", {})
                .get(self.settings.keycloak_audience, {})
                .get("roles", [])
            )
            if not isinstance(roles, list) or not all(
                isinstance(r, str) for r in roles
            ):
                raise InvalidAccessTokenError()
            blocked = claims.get("blocked", False)
            if type(blocked) is not bool:
                raise InvalidAccessTokenError("The blocked claim must be a boolean")
            name = claims.get("name") or claims.get("preferred_username")
            return CurrentUser(
                claims["sub"],
                name[:255] if isinstance(name, str) else None,
                frozenset(Role(role) for role in roles if role in Role),
                blocked,
            )
        except (JWTError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise InvalidAccessTokenError() from exc
