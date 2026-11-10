

import asyncio
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

from vibedebate.ai.contracts import AIProvider, AIUsage
from vibedebate.core.db import transaction
from vibedebate.models.analysis import LLMUsageEvent

logger = logging.getLogger(__name__)
_scope = ContextVar("llm_usage_scope", default=None)


@contextmanager
def usage_scope(
    user_id,
    operation_type,
    *,
    debate_id=None,
    chat_id=None,
    message_id=None,
):
    token = _scope.set(
        dict(
            user_id=user_id,
            operation_type=operation_type,
            debate_id=debate_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    )

    try:
        yield
    finally:
        _scope.reset(token)


class LoggedAIProvider(AIProvider):
    def __init__(
        self,
        delegate,
        factory,
        *,
        provider,
        model,
    ):
        self.delegate, self.factory = delegate, factory
        self.provider, self.model = provider, model

    async def _record(
        self,
        scope,
        started,
        usage,
        status,
    ):
        if scope is None:
            logger.error("LLM call has no accounting scope")

            return

        try:
            async with transaction(self.factory) as session:
                session.add(
                    LLMUsageEvent(
                        **scope,
                        provider=self.provider,
                        model=self.model,
                        input_tokens=usage.input_tokens if usage else 0,
                        output_tokens=usage.output_tokens if usage else 0,
                        cached_input_tokens=usage.cached_input_tokens if usage else 0,
                        reasoning_tokens=usage.reasoning_tokens if usage else 0,
                        usage_reported=usage.reported if usage else False,
                        estimated_cost=None,
                        currency="USD",
                        is_estimated=True,
                        latency_ms=max(0, round((monotonic() - started) * 1000)),
                        status=status,
                    )
                )
        except Exception:

            logger.exception("Could not persist LLM usage event")

    async def complete(
        self,
        messages,
        *,
        json_output=False,
    ):
        scope, started, usage, status = _scope.get(), monotonic(), None, "failed"

        try:
            result = await self.delegate.complete(messages, json_output=json_output)

            usage, status = result.usage, "completed"

            return result
        except asyncio.CancelledError:
            status = "cancelled"

            raise
        except Exception as exc:
            usage = getattr(exc, "usage", None)

            raise
        finally:
            await asyncio.shield(self._record(scope, started, usage, status))

    async def stream(
        self,
        messages,
    ):
        scope, started, usage, status = _scope.get(), monotonic(), None, "failed"

        try:
            async for chunk in self.delegate.stream(messages):
                if chunk.usage is not None:
                    usage = chunk.usage

                if chunk.finished:
                    status = "completed"

                yield chunk
        except (asyncio.CancelledError, GeneratorExit):
            status = "cancelled"

            raise
        except Exception as exc:
            usage = getattr(exc, "usage", None) or usage

            raise
        finally:
            await asyncio.shield(self._record(scope, started, usage, status))
