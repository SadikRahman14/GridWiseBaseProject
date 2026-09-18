"""FastAPI endpoints used by the judge; /docs provides a local request editor."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import GridWiseError
from .llm import ModelInterpreter
from .models import PlanResponse, Scenario
from .optimizer import optimize
from .settings import Settings

logger = logging.getLogger("gridwise")


def create_app(settings: Settings | None = None, interpreter=None) -> FastAPI:
    """The interpreter argument is dependency injection for isolated tests only."""

    @asynccontextmanager
    async def lifespan(app):
        # Global httpx logging can otherwise include configured URLs. Our own
        # messages intentionally exclude credentials, request content and replies.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        async with httpx.AsyncClient(follow_redirects=False) as client:
            app.state.interpreter = interpreter or ModelInterpreter(settings or Settings.from_env(), client)
            app.state.health_at = 0.0
            app.state.health_ok = False
            yield

    app = FastAPI(
        title="GridWise Energy Optimizer", version="1.0.0",
        description="LLM operator-note interpretation, deterministic guardrails, and 24-hour optimization.",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        details = [{"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]}
                   for e in exc.errors()]
        return JSONResponse(status_code=400, content={
            "error": {"code": "invalid_request", "message": "Malformed JSON or invalid request structure.",
                      "details": details},
        })

    @app.exception_handler(GridWiseError)
    async def controlled_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={
            "error": {"code": exc.code, "message": str(exc)},
        })

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        reference = uuid4().hex[:12]
        logger.error("unexpected_error reference=%s type=%s", reference, type(exc).__name__)
        return JSONResponse(status_code=500, content={
            "error": {"code": "internal_error", "message": "An internal error prevented a verified plan.",
                      "reference": reference},
        })

    @app.get("/health", responses={503: {"description": "Configured language model is not ready"}})
    async def health(request: Request):
        now = time.monotonic()
        if now - app.state.health_at > 3:
            try:
                async with asyncio.timeout(2.5):
                    app.state.health_ok = bool(await app.state.interpreter.ready())
            except Exception:
                app.state.health_ok = False
            app.state.health_at = now
        if not app.state.health_ok:
            return JSONResponse(status_code=503, content={
                "status": "not_ready", "message": "The configured language model is not available.",
            })
        return {"status": "ok"}

    @app.post("/optimize-energy", response_model=PlanResponse)
    async def optimize_energy(payload: Scenario):
        started = time.perf_counter()
        try:
            async with asyncio.timeout(28):
                interpretation = await app.state.interpreter.interpret(payload)
                interpretation.validate_for(payload)
                response = await asyncio.to_thread(optimize, payload, interpretation)
        except TimeoutError:
            return JSONResponse(status_code=500, content={
                "error": {"code": "request_timeout", "message": "A verified plan was not ready within 28 seconds."},
            })
        logger.info("optimization_completed seconds=%.3f", time.perf_counter() - started)
        return response

    return app


app = create_app()
