from pydantic import Field
from sqlalchemy import URL
from .base import EnvSettings


class DatabaseSettings(EnvSettings):
    postgres_host: str
    postgres_port: int = Field(ge=1, le=65535)
    postgres_db: str
    postgres_user: str
    postgres_password: str

    @property
    def url(
        self,
    ) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

def create_database_settings() -> DatabaseSettings:
    return DatabaseSettings()
