"""Adapter for a pinned DiffusionGemma service, via loopback HTTP or authenticated remote stdio."""

import json
import math
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .engine import InputTooLong
from .remote import RemoteClient, RemoteHTTPError, RemoteUnavailable
from .schema import CHAT_MODEL, ChatCompletionRequest

MODEL_ID = "nvidia/diffusiongemma-26B-A4B-it-NVFP4"
MODEL_REVISION = "ec4ff3df205028f4e81c954c2227f9312b3ec2ea"
SERVER_REVISION = "sha256:c131a33e9a341489649c22654fb3c5b6b8c7094ae1ffca8c8e8bee0a37a40da5"


class DiffusionUnavailable(RuntimeError):
    pass


class DiffusionHTTPError(DiffusionUnavailable):
    """A real upstream rejection, separate from a failed connection."""

    def __init__(self, status_code, body, headers=None):
        self.status_code = status_code
        self.body = body if isinstance(body, dict) else {"detail": "The model rejected this request"}
        self.headers = headers or {}
        super().__init__(f"DiffusionGemma service returned HTTP {status_code}")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DiffusionUnavailable("DiffusionGemma redirects are not followed; use a loopback origin")


class DiffusionGemmaBackend:
    def __init__(self, base_url="http://127.0.0.1:8008", max_tokens=8192, relay_command="", identity_file="/data/openjev/status.json"):
        parsed = urlparse(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("OPENJEV_DIFFUSION_URL must be a loopback HTTP origin")
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.remote = RemoteClient(json.loads(relay_command), identity_file) if relay_command else None
        self.model_id, self.revision = MODEL_ID, MODEL_REVISION
        self.status, self.error = "loading", None
        self.generation_available = False

    def _request(self, path, body=None):
        if self.remote:
            try:
                return self.remote.request(path, body)
            except RemoteHTTPError as exc:
                raise DiffusionHTTPError(exc.status_code, exc.body) from exc
            except RemoteUnavailable as exc:
                raise DiffusionUnavailable(str(exc)) from exc
        request = Request(self.base_url + path,
                          data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            # Disable environment proxies even for loopback: state stays on this machine.
            with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=180 if body else 5) as response:
                if path == "/v1/chat/completions":
                    raw = response.read(1048577)
                    if len(raw) > 1048576:
                        raise DiffusionUnavailable("DiffusionGemma returned an oversized completion")
                    result = json.loads(raw)
                else:
                    result = json.load(response)
            if not isinstance(result, dict):
                raise DiffusionUnavailable("DiffusionGemma returned an invalid response")
            return result
        except HTTPError as exc:
            if path == "/v1/chat/completions":
                try:
                    error_body = json.loads(exc.read(1048576))
                except (ValueError, UnicodeError):
                    error_body = {"detail": f"DiffusionGemma service returned HTTP {exc.code}"}
                headers = {}
                retry_after = exc.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    headers["Retry-After"] = retry_after
                raise DiffusionHTTPError(exc.code, error_body, headers) from exc
            if exc.code in {400, 422}:
                try:
                    detail = json.load(exc).get("detail", "The model rejected this request")
                except (ValueError, AttributeError):
                    detail = "The model rejected this request"
                raise InputTooLong(str(detail)) from exc
            raise DiffusionUnavailable(f"DiffusionGemma service returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise DiffusionUnavailable("Cannot reach DiffusionGemma. Check the model service; see docs/diffusiongemma.md.") from exc

    def load(self):
        try:
            models = self._request("/v1/models").get("models", [])
            if not any(isinstance(m, dict) and m.get("name", m.get("id")) == "openjev-latest" for m in models):
                raise DiffusionUnavailable("The service does not advertise the required openjev-latest model")
            if self.remote:
                identity = self._request("/openjev/identity")
                if identity.get("model") != MODEL_ID or identity.get("revision") != MODEL_REVISION or identity.get("phase") != "ready" or identity.get("image") != "razorback16/openjev@" + SERVER_REVISION:
                    raise DiffusionUnavailable("The remote model identity or readiness does not match this deployment")
            self.generation_available = any(isinstance(m, dict) and m.get("name", m.get("id")) == CHAT_MODEL for m in models)
            self.status, self.error = "ready", None
        except Exception as exc:
            self.status, self.error = "error", str(exc)
            raise

    def close(self):
        if self.remote:
            self.remote.close()

    def generate(self, request: ChatCompletionRequest):
        if not self.generation_available:
            raise DiffusionUnavailable("The upstream service does not advertise diffusiongemma-26b")
        result = self._request("/v1/chat/completions", request.model_dump())
        # Validate the promised text-only result; never turn an error or malformed
        # response into a successful empty completion.
        if (result.get("object") != "chat.completion"
                or not isinstance(result.get("id"), str) or not result["id"]
                or type(result.get("created")) is not int or result["created"] < 0
                or result.get("model") != CHAT_MODEL):
            raise DiffusionUnavailable("DiffusionGemma returned invalid completion metadata")
        choices = result.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise DiffusionUnavailable("DiffusionGemma returned an invalid completion choice")
        choice = choices[0]
        message = choice.get("message")
        if (type(choice.get("index")) is not int or choice["index"] != 0
                or choice.get("finish_reason") not in ("stop", "length")
                or not isinstance(message, dict) or message.get("role") != "assistant"
                or not isinstance(message.get("content"), str) or message.get("tool_calls")
                or len(message["content"]) > 65536):
            raise DiffusionUnavailable("DiffusionGemma returned an invalid text completion")
        usage = result.get("usage")
        if (not isinstance(usage, dict)
                or any(type(usage.get(key)) is not int or usage[key] < 0
                       for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
                or usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]
                or usage["completion_tokens"] > request.max_tokens):
            raise DiffusionUnavailable("DiffusionGemma returned invalid completion token usage")
        return result

    def evaluate(self, request):
        if any(q.type == "choice" and len(q.criteria) > 128 for q in request.questions.values()):
            raise InputTooLong("DiffusionGemma supports at most 128 options per choice question")
        started = time.perf_counter()
        payload = request.model_dump(exclude_none=True)
        payload["model"] = "openjev-latest"
        result = self._request("/v1/systemone", payload)
        answers = result.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(request.questions):
            raise DiffusionUnavailable("DiffusionGemma returned unexpected question IDs")
        for key, question in request.questions.items():
            answer = answers[key]
            if not isinstance(answer, dict) or answer.get("type") != question.type:
                raise DiffusionUnavailable("DiffusionGemma returned an unexpected answer type")
            if question.type == "noul":
                values = [answer.get("noul")]
            else:
                expected = set(question.criteria) if question.type == "choice" else {str(i) for i in range(len(question.criteria))}
                probabilities = answer.get("probabilities")
                if not isinstance(probabilities, dict) or set(probabilities) != expected:
                    raise DiffusionUnavailable("DiffusionGemma returned unexpected probability keys")
                values = list(probabilities.values()) + [answer.get("confidence")]
                if question.type == "choice" and answer.get("choice") not in expected:
                    raise DiffusionUnavailable("DiffusionGemma selected an unknown option")
                if question.type == "score":
                    score = answer.get("score")
                    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= len(expected)-1:
                        raise DiffusionUnavailable("DiffusionGemma returned an invalid score")
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise DiffusionUnavailable("DiffusionGemma returned invalid probabilities")
            if question.type != "noul" and not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-5):
                raise DiffusionUnavailable("DiffusionGemma probabilities do not sum to one")
        result["meta"] = {
            "engine": "diffusiongemma-vllm", "model_id": self.model_id, "revision": self.revision,
            "server_revision": SERVER_REVISION, "device": "cuda",
            "latency_ms": round((time.perf_counter()-started)*1000, 1),
            "questions": len(request.questions), "calibrated": False,
            "location": "remote" if self.remote else "loopback",
            "inference_ms": result.pop("_inference_ms", None),
            "confidence_method": "1 - normalized entropy",
            "note": "Label probabilities from DiffusionGemma structured reads; questions share a canvas and may influence each other.",
        }
        return result
