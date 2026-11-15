from vibedebate.services.debate.exceptions import (
    ExerciseCheckedLocallyError,
    ExerciseIssueUnavailableError,
    ExerciseKindMismatchError,
)
from random import SystemRandom
from typing import Any
from uuid import UUID

from vibedebate.ai.contracts import AIProvider
from vibedebate.ai.debate import TemplateDebateIntelligence
from vibedebate.ai.exercise_policy import exercise_kinds
from vibedebate.ai.exercises import (
    CheckRequest,
    Exercise,
    ExerciseRequest,
    Feedback,
    exercise_schema,
)
from vibedebate.ai.prompts import ENV
from vibedebate.ai.usage import usage_scope
from vibedebate.core.config import AISettings
from vibedebate.repositories.debate import DebateRepository
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.services.debate.service import DebateService


class ExerciseService:
    def __init__(
        self, service: DebateService, provider: AIProvider, settings: AISettings
    ) -> None:
        self.service = service
        self.intelligence = TemplateDebateIntelligence(provider, settings)

    async def context(
        self, current: CurrentUser, message_id: UUID, index: int
    ) -> tuple[dict[str, Any], dict[str, UUID]]:
        analysis = await self.service.analysis(current, message_id)

        if analysis["status"] != "completed" or index >= len(analysis["issues"]):
            raise ExerciseIssueUnavailableError()

        async with self.service.factory() as session:
            repo = DebateRepository(session)
            message = await repo.message(message_id)
            chat = await repo.message_chat(message_id)
            previous = await repo.previous_assistant_message(
                chat.id, message.sequence_no
            )

            context = dict(
                issue=analysis["issues"][index],
                answer=message.content,
                previous=(
                    message.reply_to_content
                    if message.reply_to_message_id
                    else (previous.content if previous else "")
                ),
                topic=chat.title,
            )
            scope = dict(
                user_id=chat.user_id,
                debate_id=chat.debate_id,
                chat_id=chat.id,
                message_id=message_id,
            )

        return context, scope

    async def generate(
        self, current: CurrentUser, message_id: UUID, request: ExerciseRequest
    ) -> Exercise:
        context, scope = await self.context(current, message_id, request.issue_index)

        kind = SystemRandom().choice(exercise_kinds(context["issue"]["type"]))

        with usage_scope(**scope, operation_type="exercise_generate"):
            result, _ = await self.intelligence._generate(
                exercise_schema(kind),
                ENV.get_template("tasks/exercise/generate.jinja").render(kind=kind),
                context,
            )

        if kind not in ("quiz", "order"):
            result = Exercise(**result.model_dump(), items=[], solution=[])

        if result.kind != kind:
            raise ExerciseKindMismatchError()

        if result.kind in ("quiz", "order"):
            permutation = list(range(len(result.items)))
            SystemRandom().shuffle(permutation)

            if permutation == result.solution:
                permutation.reverse()

            result.items = [result.items[i] for i in permutation]
            result.solution = [permutation.index(i) for i in result.solution]

        return result

    async def check(
        self, current: CurrentUser, message_id: UUID, request: CheckRequest
    ) -> Feedback:
        if request.exercise.kind in ("quiz", "order"):
            raise ExerciseCheckedLocallyError()

        context, scope = await self.context(current, message_id, request.issue_index)

        with usage_scope(**scope, operation_type="exercise_feedback"):
            result, _ = await self.intelligence._generate(
                Feedback,
                ENV.get_template("tasks/exercise/check.jinja").render(),
                dict(context=context, **request.model_dump()),
            )

        if (
            request.exercise.kind != "coach"
            or len(request.history) == 2
            or result.achieved
        ):
            result.next_question = ""

        return result
