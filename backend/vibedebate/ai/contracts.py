from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal
from pydantic import BaseModel, Field
from vibedebate.core.exceptions import ServiceUnavailableError


class AIError(ServiceUnavailableError):
    code = "ai_unavailable"
    message = "AI operation failed"

    def __init__(
        self,
        *args,
        usage=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.usage = usage


class AIMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AIUsage(BaseModel):
    reported: bool = True
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class AIResult(BaseModel):
    content: str
    usage: AIUsage = Field(default_factory=AIUsage)


class AIChunk(BaseModel):
    delta: str = ""
    usage: AIUsage | None = None
    finished: bool = False


class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[AIMessage],
        *,
        json_output: bool = False,
    ) -> AIResult: ...

    @abstractmethod
    def stream(
        self,
        messages: list[AIMessage],
    ) -> AsyncIterator[AIChunk]: ...
