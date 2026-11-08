from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[3]


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")


class DatabaseSettings(EnvSettings):
    postgres_host: str
    postgres_port: int = Field(ge=1, le=65535)
    postgres_db: str
    postgres_user: str
    postgres_password: str

    @property
    def url(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


class UserSettings(EnvSettings):
    keycloak_issuer: str
    keycloak_jwks_url: str
    keycloak_audience: str
    keycloak_client_id: str
    jwks_ttl_seconds: int = Field(default=300, ge=30)


class SeedSettings(EnvSettings):
    seed_dir: Path = Path(__file__).resolve().parents[1] / "seed"


def create_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


def create_user_settings() -> UserSettings:
    return UserSettings()


def create_seed_settings() -> SeedSettings:
    return SeedSettings()


class KeycloakAdminSettings(EnvSettings):
    keycloak_admin_api_url: str
    keycloak_admin_token_url: str
    keycloak_service_client_id: str
    keycloak_service_client_secret: str


def create_keycloak_admin_settings() -> KeycloakAdminSettings:
    return KeycloakAdminSettings()
