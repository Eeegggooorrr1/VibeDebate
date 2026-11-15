from vibedebate.ai.exceptions import AIError
import asyncio
import json
import time
from uuid import uuid4, UUID
import httpx
import pytest
from dishka import Provider, Scope, provide, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from vibedebate.core.config import (
    DatabaseSettings,
    SeedSettings,
    AISettings,
    UserSettings,
)
from vibedebate.core.di.container import (
    InfrastructureProvider,
    ApplicationProvider,
    AuthenticationProvider,
)
from vibedebate.core.di.debate import DebateProvider
from vibedebate.core.db import transaction
from vibedebate.main import create_app
from vibedebate.models import User
from vibedebate.models.debate import Debate, ChatMessage
from vibedebate.cli.bootstrap.seed_service import SeedService
from vibedebate.ai.contracts import AIProvider, AIResult, AIChunk, AIUsage
from vibedebate.ai.usage import LoggedAIProvider
from vibedebate.ai.tasks import WEIGHTS
from vibedebate.models.analysis import LLMUsageEvent
from vibedebate.services.debate.analysis import AnalysisService
from vibedebate.services.user.tokens import TokenVerifier
from vibedebate.services.user.keycloak import KeycloakUserClient
from vibedebate.services.debate.service import DebateService
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.schemas.internal.debate import PreparedTurn
from vibedebate.schemas.requests.debate import MessageCreate
from vibedebate.core.auth.roles import Role
from test_user import SETTINGS, PUBLIC, token, migrate_test_database


class FakeAI(AIProvider):
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.contexts = []
        self.analysis_contexts = []

    async def complete(self, messages, *, json_output=False):
        context = json.loads(messages[-1].content)
        if "exercise" in context:
            return AIResult(
                content=json.dumps(
                    dict(achieved=True, feedback="Valid premise", next_question="")
                )
            )

        if "issue" in context:
            data = dict(
                kind=(
                    kind := next(
                        k
                        for k in (
                            "quiz",
                            "order",
                            "premise",
                            "rewrite",
                            "coach",
                        )
                        if f"Формат строго {k}." in messages[0].content
                    )
                ),
                title="Premise",
                instruction="Choose the missing premise",
                items=["A", "B", "C"] if kind in ("quiz", "order") else [],
                solution=(
                    [1] if kind == "quiz" else [0, 1, 2] if kind == "order" else []
                ),
                explanation="B links the premises",
                criteria="Find a valid link",
            )
            if kind not in ("quiz", "order"):
                data.pop("items")
                data.pop("solution")

            return AIResult(content=json.dumps(data))

        if "messages" in context:
            self.analysis_contexts.append(context["messages"])
            if self.fail:
                raise AIError()
            return AIResult(
                content=json.dumps(
                    dict(
                        is_substantive=True,
                        overall_score=None,
                        confidence=0.8,
                        dimensions=[
                            dict(key=k, score=2, applicable=True, explanation="Reason")
                            for k in WEIGHTS
                        ],
                        strengths=["Clear claim"],
                        issues=[
                            dict(
                                type="unsupported_claim",
                                severity="medium",
                                evidence_quote=context["messages"][-1]["content"],
                                explanation="Needs evidence",
                                improvement="Give an example",
                                confidence=0.8,
                            )
                        ],
                        conduct_flags=[],
                        next_step="Add evidence",
                    )
                ),
                usage=AIUsage(input_tokens=120, output_tokens=80),
            )
        self.calls += 1
        if self.fail:
            raise AIError()
        seed = {
            "title": "Возражение",
            "description": "Конкретное возражение",
            "seed_claim": "Почему ваша позиция верна?",
        }
        if (
            "opponent_position" in messages[0].content
            and "exactly" in messages[0].content
        ):
            return AIResult(
                content=json.dumps(
                    {
                        "opponent_position": "Противоположная позиция",
                        "chats": [seed] * 3,
                    }
                )
            )
        if "previous_titles" in context:
            seed["hint"] = (
                "Build an argument for your position"
                if context["side"] == "attack"
                else None
            )
        return AIResult(
            content=json.dumps(seed), usage=AIUsage(input_tokens=40, output_tokens=30)
        )

    async def stream(self, messages):
        self.calls += 1
        self.contexts.append(messages)
        yield AIChunk(delta="Первый ")
        if self.fail:
            raise AIError()
        yield AIChunk(delta="ответ.")
        yield AIChunk(finished=True, usage=AIUsage(input_tokens=60, output_tokens=20))


def test_advanced_debate_api_to_postgresql(migrate_test_database):
    async def run():
        ai = FakeAI()

        class Config(Provider):
            @provide(scope=Scope.APP)
            def database(self) -> DatabaseSettings:
                return DatabaseSettings(postgres_db="vibedebate_test")

            @provide(scope=Scope.APP)
            def user(self) -> UserSettings:
                return SETTINGS

            @provide(scope=Scope.APP)
            def seed(self) -> SeedSettings:
                return SeedSettings()

            @provide(scope=Scope.APP, override=True)
            def verifier(self, client: httpx.AsyncClient) -> TokenVerifier:
                verifier = TokenVerifier(SETTINGS, client)
                verifier.keys, verifier.expires_at = [PUBLIC], time.monotonic() + 1000
                return verifier

            @provide(scope=Scope.APP, override=True)
            def keycloak(self) -> KeycloakUserClient:
                return object()

            @provide(scope=Scope.APP, override=True)
            def settings(self) -> AISettings:
                return AISettings(_env_file=None)

            @provide(scope=Scope.APP, override=True)
            def ai_provider(
                self, factory: async_sessionmaker[AsyncSession]
            ) -> AIProvider:
                return LoggedAIProvider(ai, factory, provider="fake", model="test")

        container = make_async_container(
            InfrastructureProvider(),
            ApplicationProvider(),
            AuthenticationProvider(),
            DebateProvider(),
            FastapiProvider(),
            Config(),
        )
        engine = await container.get(AsyncEngine)
        factory = await container.get(async_sessionmaker[AsyncSession])
        subject, other = str(uuid4()), str(uuid4())
        headers = {"Authorization": "Bearer " + token(subject)}
        stranger = {"Authorization": "Bearer " + token(other)}
        try:
            async with transaction(factory) as session:
                await SeedService(session, SeedSettings()).load_data()
                await SeedService(session, SeedSettings()).load_data()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app(container)),
                base_url="http://test",
            ) as client:
                assert (await client.get("/api/v1/debates")).status_code == 401
                topics = (await client.get("/api/v1/topics", headers=headers)).json()
                assert len(topics) >= 11
                assert (
                    len(
                        (
                            await client.get("/api/v1/topics?limit=2", headers=headers)
                        ).json()
                    )
                    == 2
                )
                category = topics[0]["category_id"]
                filtered = (
                    await client.get(
                        f"/api/v1/topics?category_id={category}", headers=headers
                    )
                ).json()
                assert all(t["category_id"] == category for t in filtered)
                assert (
                    len(
                        (
                            await client.get(
                                "/api/v1/topics/opponents", headers=headers
                            )
                        ).json()
                    )
                    == 3
                )
                path = "/api/v1/debates/advanced"
                invalid = await client.post(
                    path, headers=headers, json={"user_position": "test"}
                )
                assert invalid.status_code == 422
                assert (
                    await client.post(
                        path,
                        headers=headers,
                        json={
                            "topic_id": topics[0]["id"],
                            "custom_topic": "Both",
                            "user_position": "test",
                        },
                    )
                ).status_code == 422
                assert (
                    await client.post(
                        path,
                        headers=headers,
                        json={
                            "custom_topic": "Topic",
                            "user_position": "test",
                            "opponent_persona_id": str(uuid4()),
                        },
                    )
                ).status_code == 422
                assert (
                    await client.post(
                        path,
                        headers=headers,
                        json={"topic_id": str(uuid4()), "user_position": "test"},
                    )
                ).status_code == 422
                body = {"topic_id": topics[0]["id"], "user_position": "Моя позиция"}
                response = await client.post(path, headers=headers, json=body)
                assert response.status_code == 201, response.text
                debate = response.json()
                assert len(debate["chats"]) == 3
                assert debate["topic_title"] == topics[0]["title"]
                debate_path = "/api/v1/debates/" + debate["id"]
                assert (
                    await client.get(debate_path, headers=stranger)
                ).status_code == 404
                assert (
                    len((await client.get("/api/v1/debates", headers=headers)).json())
                    == 1
                )
                defense = debate["chats"][0]
                history_path = f'/api/v1/chats/{defense["id"]}/messages'
                initial = (await client.get(history_path, headers=headers)).json()
                assert len(initial) == 1 and initial[0]["role"] == "assistant"
                assert (
                    await client.post(
                        history_path,
                        headers=stranger | {"Idempotency-Key": "hidden"},
                        json={"content": "test"},
                    )
                ).status_code == 404
                turn_headers = headers | {"Idempotency-Key": "turn-1"}
                sent = await client.post(
                    history_path,
                    headers=turn_headers,
                    json={
                        "content": "Ответ пользователя",
                        "reply_to_message_id": initial[0]["id"],
                    },
                )
                assert (
                    sent.status_code == 200 and "event: message_completed" in sent.text
                ), sent.text
                assert sent.headers["content-type"].startswith("text/event-stream")
                calls = ai.calls
                replay = await client.post(
                    history_path,
                    headers=turn_headers,
                    json={
                        "content": "Ответ пользователя",
                        "reply_to_message_id": initial[0]["id"],
                    },
                )
                assert '"replayed": true' in replay.text and ai.calls == calls
                assert (
                    await client.post(
                        history_path,
                        headers=turn_headers,
                        json={"content": "Другой текст"},
                    )
                ).status_code == 409
                history = (await client.get(history_path, headers=headers)).json()
                assert [m["sequence_no"] for m in history] == [1, 2, 3]
                assert history[-2]["reply_to_message_id"] == initial[0]["id"]
                assert history[-2]["reply_to_content"] == initial[0]["content"]
                reference = json.loads(ai.contexts[-1][1].content.splitlines()[-1])
                assert reference == {
                    "role": "assistant",
                    "message_id": initial[0]["id"],
                    "content": initial[0]["content"],
                }
                assert ai.contexts[-1][-1].content == "Ответ пользователя"
                assert (
                    await client.post(
                        history_path,
                        headers=turn_headers,
                        json={"content": "Ответ пользователя"},
                    )
                ).status_code == 409
                assert (
                    await client.post(
                        history_path,
                        headers=headers | {"Idempotency-Key": "reply-user"},
                        json={
                            "content": "test",
                            "reply_to_message_id": history[-2]["id"],
                        },
                    )
                ).status_code == 422
                other_history = (
                    await client.get(
                        f"/api/v1/chats/{debate['chats'][1]['id']}/messages",
                        headers=headers,
                    )
                ).json()
                assert (
                    await client.post(
                        history_path,
                        headers=headers | {"Idempotency-Key": "reply-other-chat"},
                        json={
                            "content": "test",
                            "reply_to_message_id": other_history[0]["id"],
                        },
                    )
                ).status_code == 422
                assert (
                    await client.post(
                        history_path,
                        headers=headers | {"Idempotency-Key": "reply-forged"},
                        json={
                            "content": "test",
                            "reply_to_message_id": initial[0]["id"],
                            "reply_to_content": "forged quote",
                        },
                    )
                ).status_code == 422

                assert history[-1]["content"] == "Первый ответ."
                assert history[-1]["generation_status"] == "completed"
                assert (
                    len(
                        (
                            await client.get(
                                history_path + "?offset=1&limit=1", headers=headers
                            )
                        ).json()
                    )
                    == 1
                )
                analysis_path = f'/api/v1/messages/{history[-2]["id"]}/analysis'
                for _ in range(100):
                    analyzed = await client.get(analysis_path, headers=headers)
                    if analyzed.json()["status"] in ("completed", "failed"):
                        break
                    await asyncio.sleep(0.02)
                assert analyzed.status_code == 200, analyzed.text
                result = analyzed.json()
                assert result["status"] == "completed", result
                assert result["overall_score"] == 50
                quoted = json.loads(
                    ai.analysis_contexts[0][1]["content"].splitlines()[-1]
                )
                assert (
                    quoted["content"] == initial[0]["content"]
                    and quoted["role"] == "assistant"
                )
                assert ai.analysis_contexts[0][-1]["content"] == "Ответ пользователя"

                assert result["issues"][0]["evidence_quote"] == history[-2]["content"]
                assert len(result["dimensions"]) == 8
                progress = (
                    await client.get(f"/api/v1/chats/{defense['id']}", headers=headers)
                ).json()
                assert progress["scored_answers"] == 1
                assert progress["score_total"] == 50
                assert progress["good_streak"] == 0
                assert progress["mastered_at"] is None
                await client.post(analysis_path + "/retry", headers=headers)
                repeated = (
                    await client.get(f"/api/v1/chats/{defense['id']}", headers=headers)
                ).json()
                assert repeated["scored_answers"] == 1

                assert (
                    await client.get(analysis_path, headers=stranger)
                ).status_code == 404
                assert (
                    await client.post(analysis_path + "/retry", headers=stranger)
                ).status_code == 404
                assert (
                    await client.get(
                        f'/api/v1/messages/{history[-1]["id"]}/analysis',
                        headers=headers,
                    )
                ).status_code == 422
                for direction in ("attack", "defense"):
                    suggest_path = debate_path + "/chat-suggestions"
                    count_before = len(
                        (
                            await client.get(debate_path + "/chats", headers=headers)
                        ).json()
                    )
                    assert (
                        await client.post(
                            suggest_path, headers=stranger, json={"side": direction}
                        )
                    ).status_code == 404
                    suggestion = await client.post(
                        suggest_path, headers=headers, json={"side": direction}
                    )
                    assert suggestion.status_code == 200, suggestion.text
                    preview = suggestion.json()
                    regenerated = await client.post(
                        suggest_path,
                        headers=headers,
                        json={"side": direction, "previous_titles": [preview["title"]]},
                    )
                    assert regenerated.status_code == 200
                    assert (
                        len(
                            (
                                await client.get(
                                    debate_path + "/chats", headers=headers
                                )
                            ).json()
                        )
                        == count_before
                    )
                    before_accept = ai.calls
                    accepted = await client.post(
                        debate_path + "/chats",
                        headers=headers,
                        json={"side": direction, "accepted_suggestion": preview},
                    )
                    assert accepted.status_code == 201, accepted.text
                    assert ai.calls == before_accept
                    accepted_chat = accepted.json()
                    accepted_history = (
                        await client.get(
                            f'/api/v1/chats/{accepted_chat["id"]}/messages',
                            headers=headers,
                        )
                    ).json()
                    if direction == "attack":
                        assert accepted_chat["attack_hint"] == preview["hint"]
                        assert accepted_history == []
                    else:
                        assert accepted_history[0]["content"] == preview["seed_claim"]
                async with factory() as session:
                    events = (
                        await session.scalars(
                            select(LLMUsageEvent)
                            .join(User)
                            .where(User.keycloak_sub == subject)
                        )
                    ).all()
                    assert {
                        "debate_plan",
                        "chat_suggestion",
                        "opponent_reply",
                        "message_analysis",
                    } <= {e.operation_type for e in events}
                    reply_event = next(
                        e for e in events if e.operation_type == "opponent_reply"
                    )
                    assert reply_event.message_id == UUID(history[-1]["id"])
                    assert (
                        reply_event.input_tokens == 60
                        and reply_event.output_tokens == 20
                    )
                    assert (
                        reply_event.usage_reported and reply_event.status == "completed"
                    )
                    assert reply_event.estimated_cost is None
                exercise_path = f'/api/v1/messages/{history[-2]["id"]}/exercises'
                generated = await client.post(
                    exercise_path,
                    headers=headers,
                    json={"issue_index": 0},
                )
                assert generated.status_code == 200, generated.text
                assert generated.json()["kind"] in ("quiz", "rewrite")
                checked = await client.post(
                    exercise_path + "/check",
                    headers=headers,
                    json={
                        "issue_index": 0,
                        "exercise": generated.json()
                        | {"kind": "premise", "items": [], "solution": []},
                        "answer": "The missing premise",
                        "history": [],
                    },
                )
                assert checked.status_code == 200, checked.text
                assert checked.json()["achieved"] is True

                assert (
                    await client.post(
                        exercise_path,
                        headers=stranger,
                        json={"issue_index": 0},
                    )
                ).status_code == 404
                assert (
                    await client.post(
                        exercise_path,
                        headers=headers,
                        json={"issue_index": 20},
                    )
                ).status_code == 422
                new_chat = await client.post(
                    debate_path + "/chats", headers=headers, json={"side": "attack"}
                )
                assert new_chat.status_code == 201, new_chat.text
                attack = new_chat.json()
                attack_path = f'/api/v1/chats/{attack["id"]}'
                attack_turn = await client.post(
                    attack_path + "/messages",
                    headers=turn_headers,
                    json={"content": "Довод в пользу позиции"},
                )
                assert "event: message_completed" in attack_turn.text
                assert (await client.get(attack_path, headers=headers)).json()[
                    "title"
                ] == "Возражение"
                assert not any(
                    m.content == "Ответ пользователя" for m in ai.contexts[-1]
                )
                extra = await client.post(
                    debate_path + "/chats",
                    headers=headers,
                    json={"side": "defense", "title": "Новое возражение"},
                )
                assert extra.status_code == 201, extra.text
                # Provider failure preserves both the user's message and the partial response.
                ai.fail = True
                failed = await client.post(
                    history_path,
                    headers=headers | {"Idempotency-Key": "fail"},
                    json={"content": "Ещё ответ"},
                )
                assert "event: error" in failed.text
                failure_history = (
                    await client.get(history_path, headers=headers)
                ).json()
                assert failure_history[-2]["content"] == "Ещё ответ"
                assert failure_history[-1]["generation_status"] == "failed"
                assert failure_history[-1]["content"] == "Первый "
                failed_analysis_path = (
                    f'/api/v1/messages/{failure_history[-2]["id"]}/analysis'
                )
                for _ in range(100):
                    failed_analysis = (
                        await client.get(failed_analysis_path, headers=headers)
                    ).json()
                    if failed_analysis["status"] == "failed":
                        break
                    await asyncio.sleep(0.02)
                assert failed_analysis["status"] == "failed"
                async with factory() as session:
                    events = (
                        await session.scalars(
                            select(LLMUsageEvent).where(
                                LLMUsageEvent.message_id
                                == UUID(failure_history[-1]["id"])
                            )
                        )
                    ).all()
                    assert len(events) == 1 and events[0].status == "failed"
                    assert not events[0].usage_reported
                before = len(
                    (await client.get("/api/v1/debates", headers=headers)).json()
                )
                assert (
                    await client.post(
                        path,
                        headers=headers,
                        json={"custom_topic": "Своя тема", "user_position": "Позиция"},
                    )
                ).status_code == 503
                assert (
                    len((await client.get("/api/v1/debates", headers=headers)).json())
                    == before
                )
                ai.fail = False
                retried = await client.post(
                    failed_analysis_path + "/retry", headers=headers
                )
                assert retried.status_code == 200
                for _ in range(100):
                    retried_result = (
                        await client.get(failed_analysis_path, headers=headers)
                    ).json()
                    if retried_result["status"] == "completed":
                        break
                    await asyncio.sleep(0.02)
                assert retried_result["status"] == "completed"
                own = await client.post(
                    path,
                    headers=headers,
                    json={"custom_topic": "Своя тема", "user_position": "Позиция"},
                )
                assert (
                    own.status_code == 201 and own.json()["topic_title"] == "Своя тема"
                )
                # Two simultaneous reservations serialize on the chat row, without network calls in a transaction.
                async with container() as scope:
                    service = await scope.get(DebateService)
                    current = CurrentUser(
                        subject, "Test", frozenset([Role.USER]), False
                    )
                    snapshots = await asyncio.gather(
                        *[
                            service.prepare_turn(
                                current,
                                UUID(defense["id"]),
                                MessageCreate(content="Concurrent"),
                                k,
                            )
                            for k in ("concurrent-1", "concurrent-2")
                        ],
                        return_exceptions=True,
                    )
                    assert sum(isinstance(s, PreparedTurn) for s in snapshots) == 1
                    errors = [s for s in snapshots if isinstance(s, Exception)]
                    assert len(errors) == 1 and errors[0].code == "chat_busy"
                    snapshot = next(s for s in snapshots if isinstance(s, PreparedTurn))
                    await service._finish(snapshot, "", True)
                    # Replaying an in-progress turn never starts another provider call.
                    pending = await service.prepare_turn(
                        current,
                        UUID(defense["id"]),
                        MessageCreate(content="pending"),
                        "pending",
                    )
                    duplicate = await service.prepare_turn(
                        current,
                        UUID(defense["id"]),
                        MessageCreate(content="pending"),
                        "pending",
                    )
                    assert (
                        duplicate.replay
                        and duplicate.response.generation_status == "generating"
                    )
                    calls = ai.calls
                    replay_events = [
                        event async for event in service.stream_turn(duplicate)
                    ]
                    assert "message_status" in replay_events[-1] and calls == ai.calls
                    # Closing the stream immediately after its first event releases the chat.
                    stream = service.stream_turn(pending)
                    await anext(stream)
                    await stream.aclose()
                    after_close = await service.messages(
                        current, UUID(defense["id"]), 100, 0
                    )
                    assert after_close[-1].generation_status == "failed"
                    # Cancellation while waiting for the provider also persists a failed response.
                    cancelled = await service.prepare_turn(
                        current,
                        UUID(defense["id"]),
                        MessageCreate(content="cancelled"),
                        "cancelled",
                    )
                    entered = asyncio.Event()
                    original_stream = ai.stream

                    async def blocked(messages):
                        entered.set()
                        await asyncio.Event().wait()
                        yield AIChunk(
                            finished=True,
                            usage=AIUsage(input_tokens=60, output_tokens=20),
                        )

                    ai.stream = blocked

                    async def consume():
                        return [event async for event in service.stream_turn(cancelled)]

                    task = asyncio.create_task(consume())
                    await entered.wait()
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                    ai.stream = original_stream
                    after_cancel = await service.messages(
                        current, UUID(defense["id"]), 100, 0
                    )
                    assert after_cancel[-1].generation_status == "failed"
                    service.settings = AISettings(
                        ai_max_context_chars=1000, _env_file=None
                    )
                    with pytest.raises(Exception) as error:
                        await service.prepare_turn(
                            current,
                            UUID(defense["id"]),
                            MessageCreate(content="x" * 1100),
                            "too-long",
                        )
                    assert error.value.code == "context_limit_exceeded"
                async with factory() as session:
                    assert (
                        await session.scalar(
                            select(func.count())
                            .select_from(ChatMessage)
                            .where(ChatMessage.client_request_id == "too-long")
                        )
                        == 0
                    )
                # Analysis completion order must not change the chronological streak.
                from vibedebate.ai.analysis import AnalysisResult
                from vibedebate.models.analysis import MessageAnalysis
                from vibedebate.repositories.debate import DebateRepository

                progress_chat = (
                    await client.post(
                        debate_path + "/chats", headers=headers, json={"side": "attack"}
                    )
                ).json()
                pairs = []
                async with transaction(factory) as session:
                    repo = DebateRepository(session)
                    for seq in range(1, 6):
                        message = await repo.add(
                            ChatMessage(
                                chat_id=UUID(progress_chat["id"]),
                                sequence_no=seq,
                                role="user",
                                content="argument",
                                generation_status="completed",
                            )
                        )
                        analysis = await repo.add(
                            MessageAnalysis(
                                message_id=message.id, analysis_status="running"
                            )
                        )
                        pairs.append((analysis.id, message.id))
                good = AnalysisResult(
                    is_substantive=True,
                    overall_score=90,
                    confidence=1,
                    dimensions=[],
                    strengths=[],
                    issues=[],
                    conduct_flags=[],
                    next_step="",
                )
                analysis_service = await container.get(AnalysisService)
                for index, count in [(4, 0), (0, 1), (2, 1), (1, 3), (3, 5)]:
                    await analysis_service._save_analysis(*pairs[index], good)
                    state = (
                        await client.get(
                            f"/api/v1/chats/{progress_chat['id']}", headers=headers
                        )
                    ).json()
                    assert state["scored_answers"] == count
                assert (
                    state["mastered_at"]
                    and state["progress"] == 100
                    and state["good_streak"] == 3
                )
                await analysis_service._save_analysis(*pairs[0], good)
                state = (
                    await client.get(
                        f"/api/v1/chats/{progress_chat['id']}", headers=headers
                    )
                ).json()
                assert state["scored_answers"] == 5 and state["score_total"] == 450

                # An unscored question must not dilute the average or break the streak.
                async with transaction(factory) as session:
                    repo = DebateRepository(session)
                    question = await repo.add(
                        ChatMessage(
                            chat_id=UUID(progress_chat["id"]),
                            sequence_no=6,
                            role="user",
                            content="What does that mean?",
                            generation_status="completed",
                        )
                    )
                    question_analysis = await repo.add(
                        MessageAnalysis(
                            message_id=question.id, analysis_status="running"
                        )
                    )
                    question_ids = (question_analysis.id, question.id)
                unscored = good.model_copy(
                    update={"is_substantive": False, "overall_score": None}
                )
                await analysis_service._save_analysis(*question_ids, unscored)
                state = (
                    await client.get(
                        f"/api/v1/chats/{progress_chat['id']}", headers=headers
                    )
                ).json()
                assert (
                    state["scored_answers"] == 5
                    and state["score_total"] == 450
                    and state["good_streak"] == 3
                )

                # A distant reply remains a verbatim, separately attributed context block.
                original_quote = "A premise.\n\n  Whitespace, punctuation: <x> & 'quotes' — unchanged."
                async with transaction(factory) as session:
                    repo = DebateRepository(session)
                    source = await repo.add(
                        ChatMessage(
                            chat_id=UUID(progress_chat["id"]),
                            sequence_no=7,
                            role="assistant",
                            content=original_quote,
                            generation_status="completed",
                        )
                    )
                    source_id = source.id
                    for seq in range(8, 28):
                        await repo.add(
                            ChatMessage(
                                chat_id=UUID(progress_chat["id"]),
                                sequence_no=seq,
                                role="assistant" if seq % 2 else "user",
                                content="Later message",
                                generation_status="completed",
                            )
                        )
                async with container() as scope:
                    service = await scope.get(DebateService)
                    turn = await service.prepare_turn(
                        current,
                        UUID(progress_chat["id"]),
                        MessageCreate(
                            content="I agree with your premise.",
                            reply_to_message_id=source_id,
                        ),
                        "distant-reply",
                    )
                    reference = json.loads(turn.messages[1].content.splitlines()[-1])
                    assert reference["content"] == original_quote
                    assert turn.user.reply_to_content == original_quote
                    async with factory() as session:
                        context_messages, *_ = await analysis_service._analysis_context(
                            session, turn.user.id
                        )
                        assert (
                            json.loads(context_messages[1].content.splitlines()[-1])[
                                "content"
                            ]
                            == original_quote
                        )
                        assert (
                            context_messages[-1].content == "I agree with your premise."
                        )
                    await service._finish(turn, "Answer", False)

                # A successful opponent concession overrides poor statistics, without leaking its footer.
                import re

                victory_chat = (
                    await client.post(
                        debate_path + "/chats", headers=headers, json={"side": "attack"}
                    )
                ).json()
                original_stream = ai.stream

                async def conceding(messages):
                    marker = re.search(
                        r"\[\[VD_VICTORY_[0-9a-f]{32}\]\]", messages[0].content
                    ).group()
                    for char in "You have refuted my position.\n" + marker:
                        yield AIChunk(delta=char)
                    yield AIChunk(finished=True)

                ai.stream = conceding
                victory_path = f"/api/v1/chats/{victory_chat['id']}"
                sent = await client.post(
                    victory_path + "/messages",
                    headers=headers | {"Idempotency-Key": "victory"},
                    json={"content": "Decisive argument"},
                )
                assert (
                    "event: message_completed" in sent.text
                    and "VD_VICTORY" not in sent.text
                )
                state = (await client.get(victory_path, headers=headers)).json()
                assert (
                    state["mastered_at"]
                    and state["mastery_source"] == "opponent_concession"
                    and state["progress"] == 100
                )
                assert state["scored_answers"] < 5
                saved = (
                    await client.get(victory_path + "/messages", headers=headers)
                ).json()
                assert saved[-1]["content"] == "You have refuted my position."
                for _ in range(100):
                    result = (
                        await client.get(
                            f"/api/v1/messages/{saved[-2]['id']}/analysis",
                            headers=headers,
                        )
                    ).json()
                    if result["status"] in ("completed", "failed"):
                        break
                    await asyncio.sleep(0.02)
                state = (await client.get(victory_path, headers=headers)).json()
                assert (
                    state["mastery_source"] == "opponent_concession"
                    and state["progress"] == 100
                )

                replay = await client.post(
                    victory_path + "/messages",
                    headers=headers | {"Idempotency-Key": "victory"},
                    json={"content": "Decisive argument"},
                )
                assert '"replayed": true' in replay.text
                # A footer on an interrupted response must not complete a different chat.
                broken_chat = (
                    await client.post(
                        debate_path + "/chats", headers=headers, json={"side": "attack"}
                    )
                ).json()

                async def interrupted(messages):
                    marker = re.search(
                        r"\[\[VD_VICTORY_[0-9a-f]{32}\]\]", messages[0].content
                    ).group()
                    yield AIChunk(delta="Partial answer\n" + marker)
                    raise AIError()

                ai.stream = interrupted
                broken_path = f"/api/v1/chats/{broken_chat['id']}"
                await client.post(
                    broken_path + "/messages",
                    headers=headers | {"Idempotency-Key": "broken-victory"},
                    json={"content": "Argument"},
                )
                state = (await client.get(broken_path, headers=headers)).json()
                assert state["mastered_at"] is None
                ai.stream = original_stream
                # Archive hides resources while preserving rows and enforcing ownership.
                path = f"/api/v1/chats/{defense['id']}"
                assert (await client.delete(path, headers=stranger)).status_code == 404
                assert (await client.delete(path, headers=headers)).status_code == 200
                assert (await client.get(path, headers=headers)).status_code == 404
                detail = (
                    await client.get(f"/api/v1/debates/{debate['id']}", headers=headers)
                ).json()
                assert all(c["id"] != defense["id"] for c in detail["chats"])
                path = f"/api/v1/debates/{debate['id']}"
                assert (await client.delete(path, headers=headers)).status_code == 200
                assert (await client.get(path, headers=headers)).status_code == 404
                assert (
                    await client.get(f"/api/v1/chats/{attack['id']}", headers=headers)
                ).status_code == 404
        finally:
            await (await container.get(AnalysisService)).close()
            async with transaction(factory) as session:
                await session.execute(
                    delete(User).where(User.keycloak_sub.in_([subject, other]))
                )
            await container.close()

    asyncio.run(run())
