from pydantic import Field
from .base import EnvSettings


class UserSettings(EnvSettings):
    keycloak_issuer: str
    keycloak_jwks_url: str
    keycloak_audience: str
    keycloak_client_id: str
    jwks_ttl_seconds: int = Field(default=300, ge=30)

def create_user_settings() -> UserSettings:
    return UserSettings()
