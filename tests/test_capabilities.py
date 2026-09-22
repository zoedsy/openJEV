from fastapi.testclient import TestClient

from openjev.app import create_app
from openjev.config import Settings
from openjev.diffusion import DiffusionGemmaBackend
from openjev.kev import KevBackend


class CPU:
    status = "ready"
    model_id = "test-nli"
    revision = "test"


def test_cpu_capabilities_are_explicit_and_contain_no_secrets():
    settings = Settings(api_key="secret-api-key", relay_command='["secret-host-name"]')
    with TestClient(create_app(CPU(), settings)) as client:
        response = client.get("/api/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "nli"
        assert data["typed_decisions"]["available"] is True
        assert data["typed_decisions"]["question_isolation"] == "independent"
        assert data["generation"]["supported"] is False
        assert data["generation"]["available"] is False
        assert "nli" in data["generation"]["unavailable_reason"]
        assert data["images"]["supported"] is False
        assert data["limits"]["context_tokens"] == 512
        assert data["auth_required"] is True
        assert "secret-" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_diffusion_capabilities_follow_readiness_and_advertised_model():
    backend = DiffusionGemmaBackend()
    with TestClient(create_app(backend, Settings(backend="diffusiongemma"))) as client:
        data = client.get("/api/capabilities").json()
        assert data["generation"]["supported"] is True
        assert data["generation"]["available"] is False
        assert "loading" in data["generation"]["unavailable_reason"]
        backend.status = "ready"
        data = client.get("/api/capabilities").json()
        assert data["generation"]["available"] is False
        assert "advertise" in data["generation"]["unavailable_reason"]
        backend.generation_available = True
        data = client.get("/api/capabilities").json()
        assert data["generation"]["available"] is True
        assert data["generation"]["unavailable_reason"] is None
        assert data["generation"]["streaming"] is False
        assert data["generation"]["limits"]["max_output_tokens"] == 512
        assert data["typed_decisions"]["limits"]["choice_options"] == 128
        assert data["typed_decisions"]["question_isolation"] == "shared_canvas"
        assert data["limits"]["context_tokens"] == 8192
        backend.status = "error"
        data = client.get("/api/capabilities").json()
        assert data["generation"]["available"] is False
        assert data["typed_decisions"]["available"] is False


def test_kev_is_not_misreported_as_a_text_generator():
    backend = KevBackend()
    backend.status = "ready"
    with TestClient(create_app(backend, Settings(backend="kev"))) as client:
        data = client.get("/api/capabilities").json()
        assert data["typed_decisions"]["available"] is True
        assert data["typed_decisions"]["question_isolation"] == "not_verified"
        assert data["generation"]["supported"] is False
        assert "kev" in data["generation"]["unavailable_reason"]
