import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from openjev.app import create_app
from openjev.config import Settings
from openjev.diffusion import DiffusionGemmaBackend, DiffusionUnavailable, NoRedirect
from openjev.engine import InputTooLong
from openjev.schema import SystemOneRequest

BODY = {"state": "耳机坏了，我需要退款。", "questions": {
    "intent": {"type": "choice", "instructions": "顾客想做什么？", "criteria": {"refund": "退款", "buy": "购买"}},
    "broken": {"type": "noul", "instructions": "耳机坏了。"},
    "tone": {"type": "score", "instructions": "情绪如何？", "criteria": ["平静", "生气"]},
}}
RESULT = {"model": "openjev-0.1", "answers": {
    "intent": {"type": "choice", "choice": "refund", "probabilities": {"refund": .9, "buy": .1}, "confidence": .53},
    "broken": {"type": "noul", "noul": .99},
    "tone": {"type": "score", "score": .2, "probabilities": {"0": .8, "1": .2}, "legend": {"0": "平静", "1": "生气"}, "confidence": .27},
}, "usage": {"input_tokens": 123, "output_tokens": 0}}


@pytest.fixture
def upstream():
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(b'{"models":[{"name":"openjev-latest"}]}')
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps(RESULT).encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_real_http_adapter_and_playground_contract(upstream):
    url, received = upstream
    backend = DiffusionGemmaBackend(url)
    backend.load()
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client:
        response = client.post('/v1/systemone', json=BODY)
        assert response.status_code == 200, response.text
        result = response.json()
        assert received[0]['model'] == 'openjev-latest'
        assert received[0]['state'] == BODY['state']
        assert result['answers'] == RESULT['answers']
        assert result['usage'] == RESULT['usage']
        assert result['meta']['engine'] == 'diffusiongemma-vllm'
        assert result['meta']['calibrated'] is False
        status = client.get('/api/status').json()
        assert (status['device'], status['backend'], status['max_tokens']) == ('cuda', 'diffusiongemma', 8192)


@pytest.mark.parametrize('bad', [None, '0.9', True, -1, 1.1, float('nan'), float('inf')])
def test_reject_invalid_probabilities(monkeypatch, bad):
    backend = DiffusionGemmaBackend()
    result = copy.deepcopy(RESULT)
    result['answers']['broken']['noul'] = bad
    monkeypatch.setattr(backend, '_request', lambda *a: result)
    with pytest.raises(DiffusionUnavailable):
        backend.evaluate(SystemOneRequest(**BODY))


def test_reject_non_normalized_distribution(monkeypatch):
    backend = DiffusionGemmaBackend()
    result = copy.deepcopy(RESULT)
    result['answers']['intent']['probabilities']['buy'] = .9
    monkeypatch.setattr(backend, '_request', lambda *a: result)
    with pytest.raises(DiffusionUnavailable, match='sum'):
        backend.evaluate(SystemOneRequest(**BODY))


def test_choice_limit_is_explicit():
    backend = DiffusionGemmaBackend()
    body = {'state':'x', 'questions':{'x':{'type':'choice','instructions':'choose','criteria':{str(i):str(i) for i in range(129)}}}}
    with pytest.raises(InputTooLong, match='128'):
        backend.evaluate(SystemOneRequest(**body))


@pytest.mark.parametrize('url', ['https://example.com', 'http://example.com', 'http://127.0.0.1@evil.com', 'http://localhost:8008/v1', 'http://localhost?key=x'])
def test_state_cannot_leave_loopback(url):
    with pytest.raises(ValueError):
        DiffusionGemmaBackend(url)
    with pytest.raises(DiffusionUnavailable):
        NoRedirect().redirect_request(None, None, 307, 'redirect', {}, 'https://example.com')


def test_unavailable_server_is_not_a_silent_model_fallback(monkeypatch):
    backend = DiffusionGemmaBackend()
    def unavailable(*args):
        raise DiffusionUnavailable('unavailable')
    monkeypatch.setattr(backend, '_request', unavailable)
    with pytest.raises(DiffusionUnavailable):
        backend.load()
    assert backend.status == 'error'
    backend.status = 'ready'
    with TestClient(create_app(backend, Settings(backend='diffusiongemma'))) as client:
        assert client.post('/v1/systemone', json=BODY).status_code == 502


@pytest.mark.parametrize('field,value', [('phase','loading'), ('revision','wrong'), ('image','wrong')])
def test_remote_identity_must_match_pinned_ready_service(monkeypatch, field, value):
    from openjev.diffusion import MODEL_ID, MODEL_REVISION, SERVER_REVISION
    backend = DiffusionGemmaBackend()
    backend.remote = object()
    identity = dict(model=MODEL_ID, revision=MODEL_REVISION, image='razorback16/openjev@'+SERVER_REVISION, phase='ready')
    identity[field] = value
    monkeypatch.setattr(backend, '_request', lambda path, body=None: {'models':[{'name':'openjev-latest'}]} if path == '/v1/models' else identity)
    with pytest.raises(DiffusionUnavailable, match='identity'):
        backend.load()
    assert backend.status == 'error'
