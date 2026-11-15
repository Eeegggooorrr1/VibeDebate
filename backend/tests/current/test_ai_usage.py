from vibedebate.ai.exceptions import AIError
import asyncio
from uuid import uuid4
import pytest
from vibedebate.ai.contracts import AIProvider, AIChunk, AIUsage, AIResult
from vibedebate.ai.usage import LoggedAIProvider, usage_scope


class FakeProvider(AIProvider):
    async def complete(self, messages, *, json_output=False):
        raise AIError(usage=AIUsage(input_tokens=12, output_tokens=3))

    async def stream(self, messages):
        yield AIChunk(delta="partial", usage=AIUsage(input_tokens=9, output_tokens=1))
        await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_usage_failure_and_cancel_keep_scope_and_reported_tokens():
    provider = LoggedAIProvider(FakeProvider(), None, provider="test", model="test")
    events = []

    async def record(scope, started, usage, status):
        events.append((scope, usage, status))

    provider._record = record
    owner = uuid4()
    with usage_scope(owner, "suggest"):
        with pytest.raises(AIError):
            await provider.complete([])
    assert events[-1][0]["user_id"] == owner
    assert events[-1][1].output_tokens == 3
    assert events[-1][2] == "failed"
    ready = asyncio.Event()

    async def consume():
        with usage_scope(owner, "reply"):
            async for chunk in provider.stream([]):
                ready.set()

    task = asyncio.create_task(consume())
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events[-1][0]["operation_type"] == "reply"
    assert events[-1][1].input_tokens == 9
    assert events[-1][2] == "cancelled"
