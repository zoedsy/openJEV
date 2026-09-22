"""Public capabilities of the configured adapter, with no host or secret details."""

from fastapi import APIRouter

from .diffusion import DiffusionGemmaBackend
from .schema import (CHAT_DEFAULT_OUTPUT_TOKENS, CHAT_MAX_INPUT_CHARS,
                     CHAT_MAX_MESSAGE_CHARS, CHAT_MAX_MESSAGES,
                     CHAT_MAX_OUTPUT_TOKENS, CHAT_MODEL)


def generation_capability(engine, settings):
    implemented = settings.backend == "diffusiongemma" and isinstance(engine, DiffusionGemmaBackend)
    ready = getattr(engine, "status", "ready") == "ready"
    advertised = implemented and getattr(engine, "generation_available", False)
    if not implemented:
        reason = f"The {settings.backend} adapter does not implement text generation."
    elif not ready:
        reason = "The model is loading or unavailable; check /api/status."
    elif not advertised:
        reason = "The upstream service does not advertise diffusiongemma-26b."
    else:
        reason = None
    return {
        "supported": implemented,
        "available": bool(implemented and ready and advertised),
        "unavailable_reason": reason,
        "endpoint": "/v1/chat/completions",
        "model": CHAT_MODEL if implemented else None,
        "format": "OpenAI-style text-only subset",
        "availability_check": "backend readiness and upstream model advertisement",
        "supported_parameters": ["model", "messages", "max_tokens", "stream=false"],
        "streaming": False,
        "tools": False,
        "structured_output": False,
        "thinking": False,
        "limits": {
            "messages": CHAT_MAX_MESSAGES,
            "characters_per_message": CHAT_MAX_MESSAGE_CHARS,
            "input_characters": CHAT_MAX_INPUT_CHARS,
            "max_output_tokens": CHAT_MAX_OUTPUT_TOKENS,
            "default_output_tokens": CHAT_DEFAULT_OUTPUT_TOKENS,
        },
    }


def capabilities(engine, settings):
    ready = getattr(engine, "status", "ready") == "ready"
    context_tokens = (settings.max_tokens if settings.backend == "nli" else
                      settings.diffusion_max_tokens if settings.backend == "diffusiongemma" else 8192)
    return {
        "backend": settings.backend,
        "status": getattr(engine, "status", "ready"),
        "model_id": engine.model_id,
        "typed_decisions": {
            "supported": True,
            "available": ready,
            "unavailable_reason": None if ready else "The model is loading or unavailable; check /api/status.",
            "endpoint": "/v1/systemone",
            "types": ["choice", "score", "noul"],
            "calibrated": False,
            "question_isolation": "independent" if settings.backend == "nli" else
                                  "shared_canvas" if settings.backend == "diffusiongemma" else "not_verified",
            "limits": {
                "questions": 32,
                "choice_options": 128 if settings.backend == "diffusiongemma" else 255,
                "score_levels": 10,
                "candidate_evaluations": 256,
                "state_characters": 60000,
            },
        },
        "generation": generation_capability(engine, settings),
        "images": {
            "supported": False,
            "available": False,
            "unavailable_reason": "These adapters accept text and structured decision state only; image inputs are disabled.",
        },
        "limits": {
            "request_body_bytes": 262144,
            "concurrent_requests": 2,
            "context_tokens": context_tokens,
            "context_scope": "each state/question pair" if settings.backend == "nli" else "complete request, including template and output",
        },
        "auth_required": bool(settings.api_key),
    }


def create_capabilities_router(engine, settings):
    router = APIRouter()

    @router.get("/api/capabilities")
    async def get_capabilities():
        return capabilities(engine, settings)

    return router
