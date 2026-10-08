"""FastAPI application factory."""

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from weather_api.config import get_settings
from weather_api.errors import install_error_handlers
from weather_api.logging_config import configure_logging, request_id_var
from weather_api.routes import geocode, locations, me, system

log = logging.getLogger("weather_api.request")

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="WeatherNext Personal Weather API",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    install_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "If-None-Match", "X-Request-ID"],
        expose_headers=["ETag", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        incoming = (
            request.headers.get("x-request-id")
            or request.headers.get("x-cloud-trace-context", "").split("/")[0]
        )
        request_id = incoming if incoming and _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        route = request.scope.get("route")
        # Log the route template, never the query string: it can hold coordinates.
        log.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status_code": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            },
        )
        return response

    app.include_router(system.router)
    app.include_router(me.router)
    app.include_router(locations.router)
    app.include_router(geocode.router)
    return app


app = create_app()
