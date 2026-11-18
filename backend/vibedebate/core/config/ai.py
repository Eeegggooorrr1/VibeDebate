from pydantic import Field, SecretStr
from .base import EnvSettings


class AISettings(EnvSettings):
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = Field(min_length=1)
    deepseek_model: str = Field(min_length=1)
    ai_timeout_seconds: float = Field(default=90, gt=0, le=600)
    ai_max_output_tokens: int = Field(default=4096, ge=256, le=32768)
    ai_max_context_chars: int = Field(default=60000, ge=1000)
    defense_chat_count: int = Field(default=3, ge=1, le=10)
    ai_retry_count: int = Field(default=2, ge=0, le=10)
    ai_retry_base_delay_seconds: float = Field(default=0.5, ge=0, le=30)
    ai_retry_max_delay_seconds: float = Field(default=8, ge=0, le=120)


def create_ai_settings() -> AISettings:
    return AISettings()
