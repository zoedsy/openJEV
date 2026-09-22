"""Local HTTP API and dependency-free playground."""

import asyncio
import hmac
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import __version__
from .config import Settings
from .engine import InputTooLong, LocalNLI, evaluate
from .schema import SystemOneRequest
from .kev import KevBackend, KevUnavailable
from .diffusion import DiffusionGemmaBackend, DiffusionUnavailable
from .chat import create_chat_router
from .capabilities import create_capabilities_router

PACKAGE = Path(__file__).parent
log = logging.getLogger("openjev")


class BodyLimitMiddleware:
    """Bound body size even when Content-Length is omitted or incorrect."""

    def __init__(self, app, limit=262144):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                response = JSONResponse({"detail": "Request body exceeds 256 KiB"}, status_code=413)
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def create_app(scorer=None, settings=None):
    settings = settings or Settings.from_env()
    if scorer is not None:
        engine = scorer
    elif settings.backend == "diffusiongemma":
        engine = DiffusionGemmaBackend(settings.diffusion_url, settings.diffusion_max_tokens, settings.relay_command, settings.relay_identity_file)
    elif settings.backend == "kev":
        engine = KevBackend(settings.kev_url)
    else:
        engine = LocalNLI(settings)
    context_length = (settings.max_tokens if settings.backend == "nli" else
                      settings.diffusion_max_tokens if settings.backend == "diffusiongemma" else 8192)

    @asynccontextmanager
    async def lifespan(app):
        app.state.slots = asyncio.Semaphore(2)
        task = None
        if scorer is None:
            async def load():
                try:
                    await run_in_threadpool(engine.load)
                except Exception:
                    log.exception("Model loading failed; /api/status contains the error")
            task = asyncio.create_task(load())
        try:
            yield
        finally:
            if task:
                await task
            close = getattr(engine, "close", None)
            if close:
                await run_in_threadpool(close)

    app = FastAPI(title="openJEV", version=__version__, lifespan=lifespan,
                  description="Independent local Choice, Score and Noul decisions. Uncalibrated local model probabilities.")
    app.add_middleware(BodyLimitMiddleware)

    async def authorize(request: Request):
        if settings.api_key:
            expected = f"Bearer {settings.api_key}"
            if not hmac.compare_digest(request.headers.get("authorization", "").encode(), expected.encode()):
                raise HTTPException(401, "Missing or invalid API key", headers={"WWW-Authenticate": "Bearer"})

    app.include_router(create_chat_router(engine, settings, authorize))
    app.include_router(create_capabilities_router(engine, settings))

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path in {"/", "/tickets", "/static/tickets.html"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            )
        if request.url.path.startswith(("/v1/", "/api/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/status")
    async def status():
        return {
            "status": getattr(engine, "status", "ready"),
            "error": getattr(engine, "error", None),
            "version": __version__,
            "model_id": engine.model_id,
            "revision": engine.revision,
            "device": "cuda" if settings.backend == "diffusiongemma" else settings.device,
            "backend": settings.backend,
            "location": "remote" if settings.backend == "diffusiongemma" and settings.relay_command else "loopback" if settings.backend == "diffusiongemma" else "local",
            "max_tokens": context_length,
            "auth_required": bool(settings.api_key),
            "calibrated": False,
        }

    @app.get("/api/examples")
    async def examples():
        return json.loads((PACKAGE / "examples.json").read_text())

    @app.get("/v1/models", dependencies=[Depends(authorize)])
    async def models():
        available = [{"id": "openjev-local", "aliases": ["openjev-latest", "jev-latest"],
                      "model_id": engine.model_id, "context_length": context_length}]
        if isinstance(engine, DiffusionGemmaBackend) and engine.generation_available:
            available.append({"id": "diffusiongemma-26b", "model_id": engine.model_id,
                              "context_length": context_length, "capability": "text_generation"})
        return {"models": available}

    @app.post("/v1/systemone", dependencies=[Depends(authorize)])
    async def system_one(body: SystemOneRequest, request: Request):
        if getattr(engine, "status", "ready") != "ready":
            raise HTTPException(503, "Model is loading or unavailable. Check /api/status.",
                                headers={"Retry-After": "3"})
        try:
            await asyncio.wait_for(request.app.state.slots.acquire(), timeout=0.05)
        except asyncio.TimeoutError:
            raise HTTPException(429, "Local model is busy. Retry shortly.", headers={"Retry-After": "1"})
        try:
            if isinstance(engine, (KevBackend, DiffusionGemmaBackend)):
                return await run_in_threadpool(engine.evaluate, body)
            return await run_in_threadpool(evaluate, body, engine)
        except (KevUnavailable, DiffusionUnavailable) as exc:
            raise HTTPException(502, str(exc)) from exc
        except InputTooLong as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            log.exception("Inference failed")
            raise HTTPException(500, "Local inference failed. See the server log.") from exc
        finally:
            request.app.state.slots.release()

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(PACKAGE / "static" / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/tickets", include_in_schema=False)
    async def tickets():
        return FileResponse(PACKAGE / "static" / "tickets.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
    return app
