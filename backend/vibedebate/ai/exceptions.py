from vibedebate.core.exceptions import ServiceUnavailableError, UnprocessableEntityError


class AIError(ServiceUnavailableError):
    code = "ai_unavailable"
    message = "AI operation failed"

    def __init__(
        self,
        *args,
        usage=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.usage = usage


class AIInvalidResponseError(AIError):
    code = "ai_invalid_response"


class AINotConfiguredError(AIError):
    code = "ai_not_configured"
    message = "DeepSeek is not configured"


class ContextLimitExceededError(UnprocessableEntityError):
    code = "context_limit_exceeded"
    message = "Chat context limit reached"
