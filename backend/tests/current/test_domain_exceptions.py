import pytest

from vibedebate.ai.contracts import AIUsage
from vibedebate.ai.exceptions import AIError, AIInvalidResponseError
from vibedebate.services.debate.exceptions import (
    ChatBusyError,
    DebateInactiveError,
    MessageNotAnalyzableError,
    MessageNotFoundError,
    TopicUnavailableError,
)


@pytest.mark.parametrize(
    "error_type, status, code, message",
    [
        (
            DebateInactiveError,
            409,
            "debate_inactive",
            "Operation conflicts with current state",
        ),
        (MessageNotAnalyzableError, 422, "message_not_analyzable", "Invalid operation"),
        (TopicUnavailableError, 422, "topic_unavailable", "Topic is unavailable"),
        (ChatBusyError, 409, "chat_busy", "A response is already being generated"),
        (MessageNotFoundError, 404, "not_found", "Entity not found"),
    ],
)
def test_domain_errors_preserve_response_contract(
    error_type,
    status,
    code,
    message,
):
    error = error_type()

    assert (error.status_code, error.code, error.message) == (status, code, message)


def test_invalid_ai_response_preserves_usage_and_base_handler():
    usage = AIUsage(input_tokens=12, output_tokens=3)
    error = AIInvalidResponseError("Incomplete response", usage=usage)

    assert isinstance(error, AIError)
    assert error.usage is usage
    assert (error.status_code, error.code) == (503, "ai_invalid_response")
    assert str(error) == "Incomplete response"
    assert AIError().code == "ai_unavailable"
