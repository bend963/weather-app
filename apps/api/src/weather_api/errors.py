"""User-safe API errors. Internal details never reach the response body."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found(what: str = "location") -> ApiError:
    return ApiError(404, f"{what}_not_found", f"That {what} could not be found.")


def _body(code: str, message: str, request: Request) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, request), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Report which fields are wrong without echoing submitted values
        # (which could be coordinates).
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()})
        message = "Invalid request" + (f": check {', '.join(fields)}" if fields else "")
        return JSONResponse(_body("invalid_request", message, request), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(_body(code, str(exc.detail), request), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"error_category": type(exc).__name__})
        return JSONResponse(
            _body("internal_error", "Something went wrong on our side.", request), status_code=500
        )
