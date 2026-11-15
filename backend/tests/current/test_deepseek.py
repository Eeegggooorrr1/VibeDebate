from vibedebate.ai.exceptions import AIError
import json
import httpx
import pytest
from vibedebate.core.config import AISettings
from vibedebate.ai.contracts import AIMessage
from vibedebate.ai.deepseek import DeepSeekProvider
from vibedebate.ai.debate import TemplateDebateIntelligence

MESSAGES = [AIMessage(role="user", content="test")]


@pytest.mark.asyncio
async def test_deepseek_completion_and_stream_protocol():
    def handle(request):
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.url.path == "/chat/completions"
        if body["stream"]:
            return httpx.Response(
                200,
                text=': heartbeat\n\ndata: {"choices":[{"delta":{"content":"hello"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\ndata: [DONE]\n\n',
            )
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = DeepSeekProvider(
            AISettings(deepseek_api_key="test-key", _env_file=None), client
        )
        result = await provider.complete(MESSAGES, json_output=True)
        assert result.usage.input_tokens == 4
        chunks = [c async for c in provider.stream(MESSAGES)]
        assert "".join(c.delta for c in chunks) == "hello"
        assert chunks[-1].finished
        assert chunks[-2].usage.output_tokens == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "data: [DONE]\n\n",
        'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
        "data: invalid\n\n",
    ],
)
async def test_deepseek_rejects_incomplete_streams(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=payload))
    ) as client:
        provider = DeepSeekProvider(
            AISettings(deepseek_api_key="test", _env_file=None), client
        )
        with pytest.raises(AIError):
            [c async for c in provider.stream(MESSAGES)]


@pytest.mark.asyncio
async def test_deepseek_outage_and_invalid_structured_result():
    for status, data in [
        (503, {}),
        (200, {"choices": []}),
        (200, {"choices": [{"finish_reason": "stop", "message": {"content": None}}]}),
    ]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(status, json=data))
        ) as client:
            provider = DeepSeekProvider(
                AISettings(deepseek_api_key="test", _env_file=None), client
            )
            with pytest.raises(AIError):
                await provider.complete(MESSAGES)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]
                },
            )
        )
    ) as client:
        settings = AISettings(deepseek_api_key="test", _env_file=None)
        with pytest.raises(AIError, match="structured"):
            await TemplateDebateIntelligence(
                DeepSeekProvider(settings, client), settings
            ).plan({})
