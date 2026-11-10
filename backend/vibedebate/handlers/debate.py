from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from vibedebate.core.auth.annotations import AuthenticatedUser
from vibedebate.schemas.requests.debate import (
    AdvancedDebateCreate,
    ChatCreate,
    MessageCreate,
    SuggestionRequest,
)
from vibedebate.schemas.responses.debate import (
    DebateDetail,
    DebateResponse,
    ChatResponse,
    MessageResponse,
)
from vibedebate.services.debate.service import DebateService
from vibedebate.ai.debate import ChatSuggestion
from vibedebate.schemas.responses.debate import MessageAnalysisResponse

router = APIRouter(prefix="/api/v1", route_class=DishkaRoute, tags=["debates"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/debates/advanced", response_model=DebateDetail, status_code=201)
async def create_debate(
    body: AdvancedDebateCreate,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
) -> DebateDetail:
    return await service.create(user, body)


@router.get("/debates", response_model=list[DebateResponse])
async def list_debates(
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
    limit: Limit = 20,
    offset: Offset = 0,
) -> list[DebateResponse]:
    return await service.list(user, limit, offset)


@router.get("/debates/{debate_id}", response_model=DebateDetail)
async def debate_detail(
    debate_id: UUID,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
) -> DebateDetail:
    return await service.detail(user, debate_id)


@router.get("/debates/{debate_id}/chats", response_model=list[ChatResponse])
async def list_chats(
    debate_id: UUID,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
) -> list[ChatResponse]:
    return (await service.detail(user, debate_id)).chats


@router.post("/debates/{debate_id}/chats", response_model=ChatResponse, status_code=201)
async def create_chat(
    debate_id: UUID,
    body: ChatCreate,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
) -> ChatResponse:
    return await service.create_chat(user, debate_id, body)


@router.get("/chats/{chat_id}", response_model=ChatResponse)
async def chat_detail(
    chat_id: UUID,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
) -> ChatResponse:
    return await service.chat(user, chat_id)


@router.get("/chats/{chat_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    chat_id: UUID,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[MessageResponse]:
    return await service.messages(user, chat_id, limit, offset)


@router.post(
    "/chats/{chat_id}/messages",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def send_message(
    chat_id: UUID,
    body: MessageCreate,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[!-~]+$"
        ),
    ],
) -> StreamingResponse:
    snapshot = await service.prepare_turn(user, chat_id, body, idempotency_key)

    return StreamingResponse(
        service.stream_turn(snapshot),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/debates/{debate_id}/chat-suggestions", response_model=ChatSuggestion)
async def suggest_chat(
    debate_id: UUID,
    body: SuggestionRequest,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
):
    return await service.suggest(user, debate_id, body)


@router.get("/messages/{message_id}/analysis", response_model=MessageAnalysisResponse)
async def message_analysis(
    message_id: UUID,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
):
    return await service.analysis(user, message_id)


@router.post(
    "/messages/{message_id}/analysis/retry", response_model=MessageAnalysisResponse
)
async def retry_analysis(
    message_id: UUID,
    user: AuthenticatedUser,
    service: FromDishka[DebateService],
):
    return await service.analysis(user, message_id, retry=True)
