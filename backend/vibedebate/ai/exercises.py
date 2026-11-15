from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator, create_model

Kind = Literal["quiz", "order", "premise", "rewrite", "coach"]
Text = Annotated[str, Field(min_length=1, max_length=4000)]


class ExerciseContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    title: Annotated[str, Field(min_length=1, max_length=80)]
    instruction: Annotated[str, Field(min_length=1, max_length=350)]
    explanation: Text
    criteria: Text


class Exercise(ExerciseContent):
    items: list[Annotated[str, Field(min_length=1, max_length=250)]] = Field(
        max_length=6
    )
    solution: list[int] = Field(max_length=6)

    @model_validator(mode="after")
    def valid_solution(self) -> Self:
        if self.kind in ("quiz", "order"):
            if not 3 <= len(self.items) <= 6 or len(set(self.items)) != len(self.items):
                raise ValueError("Expected 3–6 distinct items")
            expected = list(range(len(self.items)))
            if self.kind == "order" and sorted(self.solution) != expected:
                raise ValueError("Order must be a permutation")
            if self.kind == "quiz" and (
                len(self.solution) != 1 or self.solution[0] not in expected
            ):
                raise ValueError("Quiz requires one valid answer")
        elif self.items or self.solution:
            raise ValueError("Open exercise has no choice items")
        return self


class ExerciseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue_index: int = Field(ge=0, le=20)


class Attempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Text
    feedback: Annotated[str, Field(max_length=4000)]


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue_index: int = Field(ge=0, le=20)
    exercise: Exercise
    answer: Text
    history: list[Attempt] = Field(default_factory=list, max_length=2)


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    achieved: bool
    feedback: Text
    next_question: Annotated[str, Field(max_length=1000)]


def exercise_schema(kind: Kind) -> type[BaseModel]:
    """Provide a format-specific contract to the model."""
    closed = kind in ("quiz", "order")

    if not closed:
        return create_model(
            f"{kind.title()}Exercise",
            __base__=ExerciseContent,
            kind=(Literal[kind], ...),
        )

    return create_model(
        f"{kind.title()}Exercise",
        __base__=Exercise,
        kind=(Literal[kind], ...),
        items=(
            list[Annotated[str, Field(min_length=1, max_length=250)]],
            Field(min_length=3 if closed else 0, max_length=6 if closed else 0),
        ),
        solution=(
            list[Annotated[int, Field(ge=0, le=5)]],
            Field(
                min_length=1 if closed else 0,
                max_length=1 if kind == "quiz" else 6 if closed else 0,
            ),
        ),
    )
