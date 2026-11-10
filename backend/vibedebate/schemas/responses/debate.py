from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import Literal
from vibedebate.ai.analysis import AnalysisDimension, AnalysisIssue


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ChatResponse(ORMResponse):
    id: UUID
    debate_id: UUID
    side: str
    title: str
    description: str
    seed_claim: str
    attack_hint: str | None = None
    opponent_persona_id: UUID
    difficulty: int
    status: str
    created_at: datetime


class DebateResponse(ORMResponse):
    id: UUID
    mode: str
    topic_id: UUID | None
    custom_topic: str | None
    topic_title: str
    user_position: str
    opponent_position: str
    status: str
    created_at: datetime


class DebateDetail(DebateResponse):
    chats: list[ChatResponse]


class MessageResponse(ORMResponse):
    id: UUID
    chat_id: UUID
    sequence_no: int
    role: str
    content: str
    generation_status: str
    client_request_id: str | None
    created_at: datetime


class MessageAnalysisResponse(BaseModel):
    message_id: UUID
    status: Literal["pending", "running", "completed", "failed"]
    is_substantive: bool | None
    overall_score: float | None
    confidence: float | None
    dimensions: list[AnalysisDimension]
    strengths: list[str]
    conduct_flags: list[str]
    issues: list[AnalysisIssue]
    next_step: str | None
