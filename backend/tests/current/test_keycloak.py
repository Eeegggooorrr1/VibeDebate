"""Exercise real Keycloak self-registration and Authorization Code + PKCE."""

import asyncio
import base64
import hashlib
import html
import re
import secrets
from urllib.parse import urlparse, parse_qs, urljoin
import httpx
from vibedebate.core.config import create_user_settings
from vibedebate.services.user.tokens import TokenVerifier


def test_keycloak_registration_pkce_and_refresh():
    settings = create_user_settings()
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    suffix = secrets.token_hex(8)
    email = f"integration-{suffix}@example.com"
    password = secrets.token_urlsafe(24)
    base = settings.keycloak_issuer
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        # Test cleanup uses the development operator account, never an application user's password grant.
        from vibedebate.core.config import EnvSettings

        class OperatorSettings(EnvSettings):
            keycloak_admin: str
            keycloak_admin_password: str

        operator = OperatorSettings()
        server = base.split("/realms/")[0]
        admin_token = client.post(
            server + "/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": operator.keycloak_admin,
                "password": operator.keycloak_admin_password,
            },
        )
        admin_token.raise_for_status()
        admin_headers = {
            "Authorization": "Bearer " + admin_token.json()["access_token"]
        }
        try:
            response = client.get(
                base + "/protocol/openid-connect/auth",
                params={
                    "client_id": settings.keycloak_client_id,
                    "redirect_uri": "http://localhost:8000/auth/callback",
                    "response_type": "code",
                    "scope": "openid",
                    "state": suffix,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                },
            )
            response.raise_for_status()
            registration = re.search(r'href="([^"]*registration[^"]*)"', response.text)
            assert registration, response.text[:300]
            # Browsers treat localhost as trustworthy; httpx otherwise withholds Secure cookies on HTTP.
            for cookie in client.cookies.jar:
                cookie.secure = False
            response = client.get(urljoin(server, html.unescape(registration.group(1))))
            action = re.search(r'<form[^>]*action="([^"]+)"', response.text)
            assert action
            response = client.post(
                urljoin(server, html.unescape(action.group(1))),
                data={
                    "email": email,
                    "username": email,
                    "firstName": "Integration",
                    "lastName": "Test",
                    "password": password,
                    "password-confirm": password,
                },
            )
            assert response.status_code in (302, 303), response.text[:1000]
            location = response.headers["location"]
            # Keycloak can redirect through a required-action completion step.
            for _ in range(5):
                if location.startswith("http://localhost:8000/auth/callback"):
                    break
                response = client.get(location)
                location = response.headers.get("location", "")
            query = parse_qs(urlparse(location).query)
            assert query.get("state") == [suffix]
            code = query["code"][0]
            response = client.post(
                base + "/protocol/openid-connect/token",
                data={
                    "client_id": settings.keycloak_client_id,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "http://localhost:8000/auth/callback",
                    "code_verifier": verifier,
                },
            )
            assert response.status_code == 200, response.text
            tokens = response.json()

            async def verify():
                async with httpx.AsyncClient(timeout=10) as http:
                    principal = await TokenVerifier(settings, http).verify_access_token(
                        tokens["access_token"]
                    )
                    assert "user" in principal.roles
                    assert "admin" not in principal.roles

            asyncio.run(verify())
            from vibedebate.core.config import KeycloakAdminSettings
            from vibedebate.services.user.keycloak import KeycloakUserClient

            async def set_blocked(blocked):
                async with httpx.AsyncClient(timeout=10) as http:
                    keycloak = KeycloakUserClient(KeycloakAdminSettings(), http)
                    current = await TokenVerifier(settings, http).verify_access_token(
                        tokens["access_token"]
                    )
                    await keycloak.set_user_blocked(current.subject, blocked=blocked)
                    # Already issued access tokens are immutable and stay valid until expiry.
                    assert not (
                        await TokenVerifier(settings, http).verify_access_token(
                            tokens["access_token"]
                        )
                    ).blocked

            asyncio.run(set_blocked(True))
            # A user cannot clear the admin-only attribute through the account API.
            account_headers = {
                "Authorization": "Bearer " + tokens["access_token"],
                "Accept": "application/json",
            }
            client.post(
                base + "/account/",
                headers=account_headers,
                json={
                    "username": email,
                    "email": email,
                    "firstName": "Integration",
                    "lastName": "Test",
                    "attributes": {"blocked": ["false"]},
                },
            )
            registered = client.get(
                server + "/admin/realms/vibedebate/users",
                headers=admin_headers,
                params={"email": email, "exact": "true"},
            )
            registered.raise_for_status()
            assert registered.json()[0]["attributes"]["blocked"] == ["true"]
            refreshed = client.post(
                base + "/protocol/openid-connect/token",
                data={
                    "client_id": settings.keycloak_client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                },
            )
            assert refreshed.status_code == 200, refreshed.text
            assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

            async def check_blocked():
                async with httpx.AsyncClient(timeout=10) as http:
                    current = await TokenVerifier(settings, http).verify_access_token(
                        refreshed.json()["access_token"]
                    )
                    assert current.blocked is True

            asyncio.run(check_blocked())
            asyncio.run(set_blocked(False))
            unblocked = client.post(
                base + "/protocol/openid-connect/token",
                data={
                    "client_id": settings.keycloak_client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": refreshed.json()["refresh_token"],
                },
            )
            assert unblocked.status_code == 200, unblocked.text

            async def check_unblocked():
                async with httpx.AsyncClient(timeout=10) as http:
                    assert (
                        await TokenVerifier(settings, http).verify_access_token(
                            unblocked.json()["access_token"]
                        )
                    ).blocked is False

            asyncio.run(check_unblocked())
            replay = client.post(
                base + "/protocol/openid-connect/token",
                data={
                    "client_id": settings.keycloak_client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                },
            )
            assert replay.status_code == 400
        finally:
            users = client.get(
                server + "/admin/realms/vibedebate/users",
                headers=admin_headers,
                params={"email": email, "exact": "true"},
            )
            users.raise_for_status()
            for user in users.json():
                deleted = client.delete(
                    server + "/admin/realms/vibedebate/users/" + user["id"],
                    headers=admin_headers,
                )
                assert deleted.status_code == 204
