import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from openjev.app import create_app
from openjev.config import Settings
from openjev.diffusion import DiffusionGemmaBackend, DiffusionUnavailable
from openjev.remote import RemoteHTTPError, RemoteUnavailable
from openjev.schema import ChatCompletionRequest

BODY = {
    "model": "diffusiongemma-26b",
    "messages": [{"role": "system", "content": "Answer briefly."},
                 {"role": "user", "content": "总结：顾客收到的杯子破损，要求退款。"}],
    "max_tokens": 32,
    "stream": False,
}
RESULT = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "created": 1790000000,
    "model": "diffusiongemma-26b",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "顾客因杯子破损要求退款。"},
                 "finish_reason": "stop", "logprobs": None}],
    "usage": {"prompt_tokens": 24, "completion_tokens": 8, "total_tokens": 32},
}


@pytest.fixture
def upstream():
    state = {"received": [], "status": 200, "response": copy.deepcopy(RESULT)}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"models":[{"name":"openjev-latest"},{"name":"diffusiongemma-26b"}]}')

        def do_POST(self):
            state["received"].append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(state["status"])
            if state["status"] == 429:
                self.send_header("Retry-After", "2")
            if state["status"] == 307:
                self.send_header("Location", "http://127.0.0.1:1/unexpected")
            self.end_headers()
            self.wfile.write(json.dumps(state["response"]).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    backend = DiffusionGemmaBackend(f"http://127.0.0.1:{server.server_port}")
    backend.load()
    try:
        yield backend, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_text_generation_real_http_contract_and_auth(upstream, monkeypatch):
    backend, state = upstream
    # A configured environment proxy must never receive the messages.
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    with TestClient(create_app(backend, Settings(backend="diffusiongemma", api_key="local-test-key"))) as client:
        assert client.post("/v1/chat/completions", json=BODY).status_code == 401
        response = client.post("/v1/chat/completions", json=BODY,
                               headers={"Authorization": "Bearer local-test-key"})
        assert response.status_code == 200, response.text
        assert response.json() == RESULT
        assert response.headers["cache-control"] == "no-store"
    assert state["received"] == [("/v1/chat/completions", BODY)]


@pytest.mark.parametrize("field,value", [
    ("stream", True), ("stream", 0), ("max_tokens", 0), ("max_tokens", 513),
    ("max_tokens", True), ("max_tokens", "32"), ("max_tokens", None),
    ("model", "openjev-latest"), ("temperature", 1), ("seed", 1),
    ("max_completion_tokens", 32), ("top_p", .9), ("tools", []),
    ("response_format", {"type": "json_object"}),
])
def test_unsupported_or_out_of_range_parameters_are_rejected(upstream, field, value):
    backend, state = upstream
    body = {**BODY, field: value}
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client:
        response = client.post("/v1/chat/completions", json=body)
        assert response.status_code == 422
    assert not state["received"]


@pytest.mark.parametrize("messages", [
    [], [{"role": "user", "content": " "}], [{"role": "tool", "content": "text"}],
    [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.invalid/image"}}]}],
    [{"role": "assistant", "content": "prefill"}],
    [{"role": "user", "content": "x"}, {"role": "system", "content": "x"}, {"role": "user", "content": "x"}],
    [{"role": "user", "content": "x", "name": "ignored?"}],
    [{"role": "user", "content": "x"}] * 33,
    [{"role": "user", "content": "x" * 16001}],
    [{"role": "user", "content": "x" * 16000}] * 3,
])
def test_text_only_message_and_input_limits(messages):
    with pytest.raises(ValueError):
        ChatCompletionRequest(messages=messages)


def test_request_defaults_are_explicit():
    body = ChatCompletionRequest(messages=[{"role": "user", "content": "Hi"}])
    assert body.model_dump() == {"model": "diffusiongemma-26b", "messages": [{"role": "user", "content": "Hi"}],
                                 "max_tokens": 128, "stream": False}


@pytest.mark.parametrize("status", [400, 422, 429, 503, 529])
def test_real_upstream_errors_preserve_status_and_body(upstream, status):
    backend, state = upstream
    error = {"error": {"message": "The upstream rejected this exact request", "type": "test_error", "code": "TEST"}}
    state.update(status=status, response=error)
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client:
        # Repeated failures release the shared request slots.
        for _ in range(3):
            response = client.post("/v1/chat/completions", json=BODY)
            assert response.status_code == status, response.text
            assert response.json() == error
        if status == 429:
            assert response.headers["retry-after"] == "2"
        state.update(status=200, response=copy.deepcopy(RESULT))
        assert client.post("/v1/chat/completions", json=BODY).status_code == 200


def test_redirect_and_oversized_body_are_rejected(upstream):
    backend, state = upstream
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client:
        assert client.post("/v1/chat/completions", content=iter([b"x" * 200000, b"x" * 70000])).status_code == 413
        assert not state["received"]
        state.update(status=307)
        response = client.post("/v1/chat/completions", json=BODY)
        assert response.status_code == 502
        assert "redirect" in response.json()["detail"].lower()
        assert len(state["received"]) == 1


def test_cpu_loading_and_unadvertised_generation_are_explicit():
    class CPU:
        model_id = "test-nli"
        revision = "test"
        status = "ready"

    with TestClient(create_app(CPU(), Settings())) as client:
        assert client.post("/v1/chat/completions", json=BODY).status_code == 501
    backend = DiffusionGemmaBackend()
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client:
        response = client.post("/v1/chat/completions", json=BODY)
        assert response.status_code == 503
        assert response.headers["retry-after"] == "3"
        backend.status = "ready"
        response = client.post("/v1/chat/completions", json=BODY)
        assert response.status_code == 501
        assert "advertise" in response.json()["detail"]


def test_remote_transport_is_used_and_real_errors_survive():
    class Transport:
        def __init__(self):
            self.received = []
            self.error = None

        def request(self, path, body=None):
            self.received.append((path, body))
            if self.error:
                raise self.error
            return copy.deepcopy(RESULT)

        def close(self):
            pass

    backend = DiffusionGemmaBackend()
    backend.status, backend.generation_available = "ready", True
    backend.remote = transport = Transport()
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client:
        assert client.post("/v1/chat/completions", json=BODY).json() == RESULT
        assert transport.received == [("/v1/chat/completions", BODY)]
        error = {"error": {"message": "Generation at capacity"}}
        transport.error = RemoteHTTPError(529, error)
        response = client.post("/v1/chat/completions", json=BODY)
        assert (response.status_code, response.json()) == (529, error)
        transport.error = RemoteUnavailable("Disconnected")
        assert client.post("/v1/chat/completions", json=BODY).status_code == 502


@pytest.mark.parametrize("change", [
    lambda r: r.update(object="chat.completion.chunk"),
    lambda r: r.update(id=""),
    lambda r: r.update(created=True),
    lambda r: r.update(model="another-model"),
    lambda r: r.update(choices=[]),
    lambda r: r["choices"][0].update(index=True),
    lambda r: r["choices"][0].update(finish_reason=None),
    lambda r: r["choices"][0].update(finish_reason=[]),
    lambda r: r["choices"][0].update(message={"role": "assistant", "content": None}),
    lambda r: r["choices"][0]["message"].update(tool_calls=[{"id": "unrequested"}]),
    lambda r: r["usage"].update(total_tokens=1),
    lambda r: r["usage"].update(completion_tokens=True),
    lambda r: r.update(usage={"prompt_tokens": 24, "completion_tokens": 513, "total_tokens": 537}),
])
def test_malformed_or_over_budget_completions_fail_closed(monkeypatch, change):
    backend = DiffusionGemmaBackend()
    backend.generation_available = True
    result = copy.deepcopy(RESULT)
    change(result)
    monkeypatch.setattr(backend, "_request", lambda *args: result)
    with pytest.raises(DiffusionUnavailable):
        backend.generate(ChatCompletionRequest(**BODY))


def test_typed_requests_and_generation_share_concurrency_budget():
    started = threading.Barrier(3)
    release = threading.Event()

    class BlockingBackend(DiffusionGemmaBackend):
        def block(self):
            started.wait(timeout=5)
            release.wait(timeout=5)

        def generate(self, request):
            self.block()
            return copy.deepcopy(RESULT)

        def evaluate(self, request):
            self.block()
            return {"answers": {"x": {"type": "noul", "noul": .5}}}

    backend = BlockingBackend()
    backend.status, backend.generation_available = "ready", True
    decision = {"state": "x", "questions": {"x": {"type": "noul", "instructions": "x"}}}
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client, ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(client.post, "/v1/chat/completions", json=BODY),
                   pool.submit(client.post, "/v1/systemone", json=decision)]
        started.wait(timeout=5)
        try:
            assert client.post("/v1/chat/completions", json=BODY).status_code == 429
            assert client.post("/v1/systemone", json=decision).status_code == 429
        finally:
            release.set()
        assert all(future.result().status_code == 200 for future in futures)
