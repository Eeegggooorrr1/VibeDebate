from dataclasses import dataclass


from abc import ABC, abstractmethod
from typing import Annotated, Any, TypeVar
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from vibedebate.core.config import AISettings
from vibedebate.core.exceptions import UnprocessableEntityError
from vibedebate.ai.contracts import AIProvider, AIMessage, AIError, AIUsage
from vibedebate.ai.prompts import render_task, plan_task, structured_messages

Text = Annotated[str, Field(min_length=1, max_length=4000)]
StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class ChatSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=300)
    description: Text
    seed_claim: Text


class ChatSuggestion(ChatSeed):
    hint: str | None = Field(default=None, min_length=1, max_length=4000)


class DebatePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    opponent_position: Text
    chats: list[ChatSeed] = Field(min_length=1, max_length=10)


class DebateIntelligence(ABC):
    @abstractmethod
    async def plan(
        self,
        context: dict[str, Any],
    ) -> tuple[DebatePlan, AIUsage]: ...

    @abstractmethod
    async def seed(
        self,
        context: dict[str, Any],
    ) -> tuple[ChatSeed, AIUsage]: ...

    @abstractmethod
    async def suggest(
        self,
        context: dict[str, Any],
    ) -> tuple[ChatSuggestion, AIUsage]: ...


def check_context(
    messages: list[AIMessage],
    settings: AISettings,
) -> None:
    if sum(len(m.content) for m in messages) > settings.ai_max_context_chars:
        raise UnprocessableEntityError(
            "Chat context limit reached", code="context_limit_exceeded"
        )


@dataclass
class TemplateDebateIntelligence(DebateIntelligence):
    provider: AIProvider
    settings: AISettings

    async def _generate(
        self,
        schema: type[StructuredResult],
        task: str,
        context: dict[str, Any],
    ) -> tuple[StructuredResult, AIUsage]:
        messages = structured_messages(task, schema.model_json_schema(), context)
        check_context(messages, self.settings)
        result = await self.provider.complete(messages, json_output=True)

        try:
            return schema.model_validate_json(result.content), result.usage
        except ValidationError as exc:
            raise AIError(
                "Invalid structured AI response", code="ai_invalid_response"
            ) from exc

    async def plan(
        self,
        context: dict[str, Any],
    ) -> tuple[DebatePlan, AIUsage]:
        plan, usage = await self._generate(
            DebatePlan, plan_task(self.settings.defense_chat_count), context
        )

        if len(plan.chats) != self.settings.defense_chat_count:
            raise AIError(
                "Incorrect number of defense chats", code="ai_invalid_response"
            )

        return plan, usage

    async def seed(
        self,
        context: dict[str, Any],
    ) -> tuple[ChatSeed, AIUsage]:
        if context.get("side") == "defense":
            context = {
                "side": "defense",
                "topic": context.get("topic", ""),
                "ai_thesis": "\n".join(
                    filter(None, (context.get("title"), context.get("description")))
                ),
                "persona": context.get("persona", {}),
                "difficulty": context.get("difficulty", 1),
            }

        return await self._generate(
            ChatSeed,
            render_task(
                "attack" if context.get("side") == "attack" else "defense",
                context=context,
            ),
            context,
        )

    async def suggest(
        self,
        context: dict[str, Any],
    ) -> tuple[ChatSuggestion, AIUsage]:
        if context["side"] == "attack":
            context = {k: v for k, v in context.items() if k != "opponent_position"}

        result, usage = await self._generate(
            ChatSuggestion, render_task("suggest", context=context), context
        )

        if context["side"] == "attack" and not result.hint:
            raise AIError(
                "Attack suggestion requires a hint", code="ai_invalid_response"
            )

        if context["side"] == "defense":
            result.hint = None

        return result, usage
