"""Business exceptions and global FastAPI exception handler."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(Exception):  # noqa: N818
    """Base application exception.

    N818 wants an ...Error suffix; skipped here because every subclass below
    already carries it (NotFoundError, ForbiddenError, UnauthorizedError,
    ConflictError, ValidationError) and the global handler matches by type,
    not by name. The rule stays enforced for every future exception.
    """

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    @property
    def headers(self) -> dict[str, str] | None:
        """Response headers this failure carries, if any.

        A hook rather than a branch in the handler: the second exception that
        needs one would otherwise start a type ladder inside the one place that
        is supposed to treat them all alike.
        """
        return None


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ForbiddenError(AppException):
    """Access denied."""

    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(message, status_code=403)


class UnauthorizedError(AppException):
    """Authentication required or invalid."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=401)


class ConflictError(AppException):
    """Resource already exists or conflict."""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409)


class ValidationError(AppException):
    """Business validation error."""

    def __init__(self, message: str = "Validation error") -> None:
        super().__init__(message, status_code=422)


class RateLimitError(AppException):
    """Too many requests from one client on one bucket."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("too many requests", status_code=429)
        self.retry_after_seconds = retry_after_seconds

    @property
    def headers(self) -> dict[str, str] | None:
        return {"Retry-After": str(self.retry_after_seconds)}


def register_exception_handlers(app: FastAPI) -> None:
    """Register the global AppException and request-validation handlers."""

    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """422 without the rejected value.

        Pydantic v2 puts the offending input in every error entry, so the
        default handler echoes whatever was posted — including a password. The
        client stores that body on ServiceError.cause and console.errors it, so
        the echo does not stay on the wire. Only the field and the reason leave.
        """
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"type": error["type"], "loc": list(error["loc"]), "msg": error["msg"]}
                    for error in exc.errors()
                ]
            },
        )
