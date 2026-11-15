from vibedebate.core.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)


class DebateInactiveError(ConflictError):
    code = "debate_inactive"


class ChatInactiveError(ConflictError):
    code = "chat_inactive"


class MessageNotAnalyzableError(UnprocessableEntityError):
    code = "message_not_analyzable"


class ExerciseIssueUnavailableError(UnprocessableEntityError):
    code = "exercise_issue_unavailable"


class ExerciseKindMismatchError(UnprocessableEntityError):
    code = "exercise_kind_mismatch"


class ExerciseCheckedLocallyError(UnprocessableEntityError):
    code = "exercise_checked_locally"


class InvalidReplyTargetError(UnprocessableEntityError):
    code = "invalid_reply_target"


class TopicUnavailableError(UnprocessableEntityError):
    code = "topic_unavailable"
    message = "Topic is unavailable"


class OpponentUnavailableError(UnprocessableEntityError):
    code = "opponent_unavailable"
    message = "Opponent or difficulty unavailable"


class DebateNotFoundError(NotFoundError):
    code = "debate_not_found"


class ChatNotFoundError(NotFoundError):
    code = "chat_not_found"


class IdempotencyConflictError(ConflictError):
    code = "idempotency_conflict"
    message = "Idempotency key was used for another message"


class ChatBusyError(ConflictError):
    code = "chat_busy"
    message = "A response is already being generated"


class MessageNotFoundError(NotFoundError):
    code = "not_found"


class MessageChatNotFoundError(NotFoundError):
    code = "not_found"
