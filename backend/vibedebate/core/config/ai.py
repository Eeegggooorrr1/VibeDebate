from pydantic import Field, SecretStr
from .base import EnvSettings


class AISettings(EnvSettings):
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    ai_timeout_seconds: float = Field(default=90, gt=0, le=600)
    ai_max_output_tokens: int = Field(default=4096, ge=256, le=32768)
    ai_max_context_chars: int = Field(default=60000, ge=1000)
    defense_chat_count: int = Field(default=3, ge=1, le=10)

def create_ai_settings() -> AISettings:
    return AISettings()
