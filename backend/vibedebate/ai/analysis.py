from abc import ABC, abstractmethod
from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from vibedebate.ai.contracts import AIMessage


class AnalysisDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    score: int | None = Field(ge=0, le=4)
    applicable: bool
    explanation: str

    @model_validator(mode="after")
    def applicable_score(
        self,
    ) -> Self:
        if self.applicable != (self.score is not None):
            raise ValueError("Only applicable dimensions have scores")

        return self


class AnalysisIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    severity: Literal["low", "medium", "high"]
    evidence_quote: str
    explanation: str
    improvement: str
    confidence: float = Field(ge=0, le=1)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_substantive: bool
    overall_score: float | None = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    dimensions: list[AnalysisDimension]
    strengths: list[str]
    issues: list[AnalysisIssue]
    conduct_flags: list[str]
    next_step: str

    @model_validator(mode="after")
    def substantive_score(
        self,
    ) -> Self:
        if not self.is_substantive and self.overall_score is not None:
            raise ValueError("Non-substantive messages must not receive a score")

        return self


class MessageAnalyzer(ABC):
    @abstractmethod
    async def analyze(
        self,
        messages: list[AIMessage],
    ) -> AnalysisResult: ...
