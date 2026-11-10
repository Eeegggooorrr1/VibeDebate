from typing import Any


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        extra: Any | None = None,
    ) -> None:
        self.message = self.message if message is None else message
        self.code = self.code if code is None else code
        self.status_code = self.status_code if status_code is None else status_code
        self.extra = extra
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "Bad request"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Authentication failed"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Entity not found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Operation conflicts with current state"


class UnprocessableEntityError(AppError):
    status_code = 422
    code = "unprocessable_entity"
    message = "Invalid operation"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Service is unavailable"
