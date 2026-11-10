from dataclasses import dataclass
import json
from collections.abc import AsyncIterator
import httpx
from pydantic import ValidationError
from vibedebate.core.config import AISettings
from vibedebate.ai.contracts import (
    AIProvider,
    AIMessage,
    AIResult,
    AIChunk,
    AIUsage,
    AIError,
)


@dataclass
class DeepSeekProvider(AIProvider):
    settings: AISettings
    client: httpx.AsyncClient

    def _request(
        self,
        messages: list[AIMessage],
        *,
        stream: bool,
        json_output: bool = False,
    ) -> dict:
        if not self.settings.deepseek_api_key:
            raise AIError("DeepSeek is not configured", code="ai_not_configured")

        body = {
            "model": self.settings.deepseek_model,
            "messages": [m.model_dump() for m in messages],
            "stream": stream,
            "max_tokens": self.settings.ai_max_output_tokens,
            "thinking": {"type": "disabled"},
        }

        if stream:
            body["stream_options"] = {"include_usage": True}

        if json_output:
            body["response_format"] = {"type": "json_object"}

        return dict(
            url=self.settings.deepseek_base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": "Bearer "
                + self.settings.deepseek_api_key.get_secret_value()
            },
            json=body,
            timeout=self.settings.ai_timeout_seconds,
        )

    @staticmethod
    def _usage(
        value: dict | None,
    ) -> AIUsage:
        reported = value is not None
        value = value or {}

        return AIUsage(
            reported=reported,
            cached_input_tokens=value.get("prompt_cache_hit_tokens", 0),
            reasoning_tokens=(value.get("completion_tokens_details") or {}).get(
                "reasoning_tokens", 0
            ),
            input_tokens=value.get("prompt_tokens", 0),
            output_tokens=value.get("completion_tokens", 0),
        )

    async def complete(
        self,
        messages: list[AIMessage],
        *,
        json_output: bool = False,
    ) -> AIResult:
        try:
            response = await self.client.post(
                **self._request(messages, stream=False, json_output=json_output)
            )
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]

            if (
                choice["finish_reason"] != "stop"
                or not choice["message"]["content"].strip()
            ):
                raise AIError(
                    "AI response is incomplete",
                    code="ai_invalid_response",
                    usage=self._usage(data.get("usage")),
                )

            return AIResult(
                content=choice["message"]["content"],
                usage=self._usage(data.get("usage")),
            )
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            ValidationError,
        ) as exc:
            raise AIError() from exc

    async def stream(
        self,
        messages: list[AIMessage],
    ) -> AsyncIterator[AIChunk]:
        finished = False

        try:
            async with self.client.stream(
                "POST", **self._request(messages, stream=True)
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue

                    payload = line[5:].strip()

                    if payload == "[DONE]":
                        if not finished:
                            raise AIError(
                                "AI stream ended prematurely",
                                code="ai_invalid_response",
                            )

                        yield AIChunk(finished=True)

                        return

                    chunk, stopped = self._parse_stream_payload(payload)
                    finished = finished or stopped
                    yield chunk

            raise AIError("AI stream ended prematurely", code="ai_invalid_response")
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            ValidationError,
        ) as exc:
            raise AIError() from exc

    def _parse_stream_payload(
        self,
        payload: str,
    ) -> tuple[AIChunk, bool]:
        finished = False
        data = json.loads(payload)
        choices = data.get("choices", [])
        delta = ""

        if choices:
            choice = choices[0]
            delta = choice.get("delta", {}).get("content") or ""
            reason = choice.get("finish_reason")

            if reason is not None:
                if reason != "stop":
                    raise AIError(
                        "AI response is incomplete",
                        code="ai_invalid_response",
                        usage=self._usage(data.get("usage")),
                    )

                finished = True

        return AIChunk(
            delta=delta,
            usage=self._usage(data["usage"]) if data.get("usage") else None,
        ), finished
