from vibedebate.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    ConflictError,
    UnprocessableEntityError,
    UnauthorizedError,
    ServiceUnavailableError,
)


class InvalidAccessTokenError(UnauthorizedError):
    code = "invalid_token"
    message = "A valid access token is required"


class UserProviderUnavailableError(ServiceUnavailableError):
    code = "user_unavailable"
    message = "User provider is unavailable"


class UserBlockedError(ForbiddenError):
    code = "user_blocked"
    message = "User is blocked"


class UserDeletedError(ForbiddenError):
    code = "user_deleted"
    message = "User is deleted"


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    message = "User not found"


class SelfBlockingError(ConflictError):
    code = "self_blocking_forbidden"
    message = "You cannot block your own account"


class SelfUnblockingError(ConflictError):
    code = "self_unblocking_forbidden"
    message = "You cannot unblock your own account"


class DeletedUserStatusChangeError(ConflictError):
    code = "deleted_user_status_change"
    message = "A deleted account cannot be blocked or unblocked"


class InvalidProfileInterestsError(UnprocessableEntityError):
    code = "invalid_profile_interests"
    message = "Profile interests must refer to active categories"
