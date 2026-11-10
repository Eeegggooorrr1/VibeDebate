from dataclasses import dataclass
from pydantic import BaseModel
from vibedebate.ai.analysis import MessageAnalyzer, AnalysisResult
from vibedebate.ai.contracts import AIMessage, AIUsage, AIError
from vibedebate.ai.debate import TemplateDebateIntelligence
from vibedebate.ai.prompts import render_task

WEIGHTS = dict(
    claim_clarity=10,
    relevance=15,
    logical_validity=20,
    evidence_quality=15,
    factual_accuracy=10,
    conceptual_precision=10,
    counterargument_handling=15,
    calibration=5,
)


@dataclass
class TemplateMessageAnalyzer(MessageAnalyzer):
    intelligence: TemplateDebateIntelligence

    async def analyze(
        self,
        messages: list[AIMessage],
    ) -> AnalysisResult:
        result, _ = await self.analyze_with_usage(messages)

        return result

    async def analyze_with_usage(
        self,
        messages: list[AIMessage],
    ) -> tuple[AnalysisResult, AIUsage]:
        if not messages or messages[-1].role != "user":
            raise ValueError("Analysis must end with the evaluated user message")

        result, usage = await self.intelligence._generate(
            AnalysisResult,
            render_task("analysis"),
            {"messages": [m.model_dump() for m in messages]},
        )

        keys = [d.key for d in result.dimensions]

        if len(keys) != len(WEIGHTS) or set(keys) != set(WEIGHTS):
            raise AIError("Invalid analysis dimensions", code="ai_invalid_response")

        if any(
            not i.evidence_quote.strip() or i.evidence_quote not in messages[-1].content
            for i in result.issues
        ):
            raise AIError(
                "Analysis evidence does not match the message",
                code="ai_invalid_response",
            )

        applicable = [d for d in result.dimensions if d.applicable]
        result.overall_score = (
            round(
                100
                * sum(d.score / 4 * WEIGHTS[d.key] for d in applicable)
                / sum(WEIGHTS[d.key] for d in applicable),
                2,
            )
            if applicable and result.is_substantive
            else None
        )

        return result, usage


class ChatSummary(BaseModel):
    summary: str


@dataclass
class ContextSummarizer:
    intelligence: TemplateDebateIntelligence

    async def summarize(
        self,
        context: dict,
        messages: list[AIMessage],
        previous_summary: str = "",
        *,
        max_chars: int = 6000,
    ) -> tuple[ChatSummary, AIUsage]:
        if not 500 <= max_chars <= 12000:
            raise ValueError("Summary budget must be between 500 and 12000 characters")

        result, usage = await self.intelligence._generate(
            ChatSummary,
            render_task("summary", max_chars=max_chars),
            {
                "context": context,
                "previous_summary": previous_summary,
                "messages": [m.model_dump() for m in messages],
            },
        )

        if len(result.summary) > max_chars:
            raise AIError(
                "Summary exceeds the requested budget", code="ai_invalid_response"
            )

        return result, usage
