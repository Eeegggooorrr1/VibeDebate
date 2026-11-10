from typing import Annotated, Literal, Self
from uuid import UUID
from vibedebate.ai.debate import ChatSuggestion
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DebateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AdvancedDebateCreate(DebateInput):
    topic_id: UUID | None = None
    custom_topic: str | None = Field(default=None, min_length=1, max_length=2000)
    user_position: str = Field(min_length=1, max_length=4000)
    opponent_persona_id: UUID | None = None
    difficulty: Literal[1, 2, 3] = 1

    @model_validator(mode="after")
    def exactly_one_topic(
        self,
    ) -> Self:
        if (self.topic_id is None) == (self.custom_topic is None):
            raise ValueError("Specify exactly one of topic_id and custom_topic")

        return self


class SuggestionRequest(DebateInput):
    side: Literal["attack", "defense"]
    title: str = Field(default="", max_length=300)
    opponent_persona_id: UUID | None = None
    difficulty: Literal[1, 2, 3] = 1
    previous_titles: list[Annotated[str, Field(max_length=300)]] = Field(
        default_factory=list, max_length=10
    )


class ChatCreate(DebateInput):
    accepted_suggestion: ChatSuggestion | None = None
    side: Literal["attack", "defense"]
    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=2000)
    opponent_persona_id: UUID | None = None
    difficulty: Literal[1, 2, 3] = 1

    @model_validator(mode="after")
    def defense_needs_topic(
        self,
    ) -> Self:
        if self.side == "defense" and not (
            self.title or self.description or self.accepted_suggestion
        ):
            raise ValueError("Defense requires a title or description")

        if (
            self.accepted_suggestion
            and self.side == "attack"
            and not self.accepted_suggestion.hint
        ):
            raise ValueError("Attack suggestion requires a hint")

        return self


class MessageCreate(DebateInput):
    content: str = Field(min_length=1, max_length=12000)
