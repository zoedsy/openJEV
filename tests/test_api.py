import json
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from openjev.app import create_app
from openjev.config import Settings
from openjev.engine import InputTooLong, Prediction


class FakeScorer:
    model_id = "test-only"
    revision = "test"
    status = "ready"

    def predict(self, pairs):
        return Prediction([(2, 0, -2)] * len(pairs), 123)


BODY = {"state": "hello", "questions": {"x": {"type": "noul", "instructions": "greeting"}}}


def test_api_and_static_end_to_end():
    with TestClient(create_app(FakeScorer())) as client:
        response = client.post("/v1/systemone", json=BODY)
        assert response.status_code == 200
        assert 0 <= response.json()["answers"]["x"]["noul"] <= 1
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/status").json()["status"] == "ready"
        assert client.get("/v1/models").json()["models"][0]["id"] == "openjev-local"
        assert client.get("/api/examples").json()[1]["id"] == "chinese"
        assert "Small questions." in client.get("/").text
        assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]
        assert client.get("/static/app.js").status_code == 200
        assert client.post("/v1/systemone", json={"state": "x", "questions": {}}).status_code == 422
        assert client.post("/v1/systemone", content="{invalid", headers={"Content-Type":"application/json"}).status_code == 422


def test_authentication_and_secret_not_exposed():
    with TestClient(create_app(FakeScorer(), Settings(api_key="test-secret"))) as client:
        assert client.post("/v1/systemone", json=BODY).status_code == 401
        assert client.get("/v1/models").status_code == 401
        assert client.post("/v1/systemone", json=BODY, headers={"Authorization":"Bearer wrong"}).status_code == 401
        assert client.post("/v1/systemone", json=BODY, headers={"Authorization":"Bearer test-secret"}).status_code == 200
        status = client.get("/api/status")
        assert status.json()["auth_required"] is True
        assert "test-secret" not in status.text


def test_loading_returns_retryable_error():
    scorer = FakeScorer()
    scorer.status = "loading"
    with TestClient(create_app(scorer)) as client:
        response = client.post("/v1/systemone", json=BODY)
        assert response.status_code == 503
        assert response.headers["retry-after"] == "3"


def test_token_limit_is_explicit_not_truncated():
    class LongScorer(FakeScorer):
        def predict(self, pairs):
            raise InputTooLong("513 tokens exceeds 512. Nothing was truncated.")
    with TestClient(create_app(LongScorer())) as client:
        response = client.post("/v1/systemone", json=BODY)
        assert response.status_code == 422
        assert "Nothing was truncated" in response.json()["detail"]


def test_request_body_limit_including_chunked_input():
    with TestClient(create_app(FakeScorer())) as client:
        assert client.post("/v1/systemone", content=b"x" * 262145).status_code == 413
        assert client.post("/v1/systemone", content=iter([b"x" * 200000, b"x" * 70000])).status_code == 413


def test_all_examples_satisfy_public_contract():
    with TestClient(create_app(FakeScorer())) as client:
        for example in client.get("/api/examples").json():
            response = client.post("/v1/systemone", json={key:example[key] for key in ("state", "questions")})
            assert response.status_code == 200, response.text
            assert set(response.json()["answers"]) == set(example["questions"])


def test_busy_server_rejects_excess_work():
    started = threading.Barrier(3)
    release = threading.Event()
    class BlockingScorer(FakeScorer):
        def predict(self, pairs):
            started.wait(timeout=5)
            release.wait(timeout=5)
            return super().predict(pairs)
    with TestClient(create_app(BlockingScorer())) as client, ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(client.post, "/v1/systemone", json=BODY) for _ in range(2)]
        started.wait(timeout=5)
        try:
            assert client.post("/v1/systemone", json=BODY).status_code == 429
        finally:
            release.set()
        assert all(f.result().status_code == 200 for f in futures)
