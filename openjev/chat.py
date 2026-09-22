"""Bounded text generation using the same authentication and slots as decisions."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .capabilities import generation_capability
from .diffusion import DiffusionHTTPError, DiffusionUnavailable
from .engine import InputTooLong
from .schema import ChatCompletionRequest

log = logging.getLogger("openjev")


def create_chat_router(engine, settings, authorize):
    router = APIRouter()

    @router.post("/v1/chat/completions", dependencies=[Depends(authorize)])
    async def chat_completions(body: ChatCompletionRequest, request: Request):
        capability = generation_capability(engine, settings)
        if not capability["supported"]:
            raise HTTPException(501, capability["unavailable_reason"])
        if getattr(engine, "status", "ready") != "ready":
            raise HTTPException(503, capability["unavailable_reason"], headers={"Retry-After": "3"})
        if not capability["available"]:
            raise HTTPException(501, capability["unavailable_reason"])
        try:
            await asyncio.wait_for(request.app.state.slots.acquire(), timeout=0.05)
        except asyncio.TimeoutError:
            raise HTTPException(429, "Local model is busy. Retry shortly.", headers={"Retry-After": "1"})
        try:
            return await run_in_threadpool(engine.generate, body)
        except DiffusionHTTPError as exc:
            return JSONResponse(exc.body, status_code=exc.status_code, headers=exc.headers)
        except DiffusionUnavailable as exc:
            raise HTTPException(502, str(exc)) from exc
        except InputTooLong as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            log.exception("Text generation failed")
            raise HTTPException(500, "Text generation failed. See the server log.") from exc
        finally:
            request.app.state.slots.release()

    return router
