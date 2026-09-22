import pytest

from openjev.kev import KevBackend, KevUnavailable
from openjev.schema import SystemOneRequest


@pytest.mark.parametrize("url", ["https://api.example.com", "http://example.com", "http://127.0.0.1@evil.com", "file:///tmp/test", "http://localhost:8009/private", "http://localhost:8009?redirect=x"])
def test_remote_backends_rejected(url):
    with pytest.raises(ValueError):
        KevBackend(url)


def test_kev_contract_mapping(monkeypatch):
    backend = KevBackend()
    seen = []
    def upstream(path, body=None):
        seen.append((path, body))
        if body is None:
            return {"models":[{"id":"kev-latest", "run":"jaredpalmer/kev-0.5b"}]}
        return {"model":"kev-latest", "answers":{"a":{"type":"noul", "noul":.75}}, "usage":{"input_tokens":20,"output_tokens":10}}
    monkeypatch.setattr(backend, "_request", upstream)
    backend.load()
    result = backend.evaluate(SystemOneRequest(state="hello",questions={"a":{"type":"noul","instructions":"greeting"}}))
    assert seen[-1][1]["model"] == "kev-latest"
    assert result["meta"]["engine"] == "kev"
    assert result["meta"]["calibrated"] is False
    assert result["answers"]["a"]["noul"] == .75


def test_invalid_upstream_values_are_not_displayed(monkeypatch):
    backend = KevBackend()
    monkeypatch.setattr(backend, "_request", lambda *args: {"answers":{"a":{"type":"noul","noul":float('nan')}}})
    with pytest.raises(KevUnavailable):
        backend.evaluate(SystemOneRequest(state="hi", questions={"a":{"type":"noul","instructions":"greeting"}}))


def test_redirects_cannot_send_state_off_machine():
    from openjev.kev import NoRedirect
    with pytest.raises(KevUnavailable, match="loopback"):
        NoRedirect().redirect_request(None,None,307,"redirect",{},"https://remote.example")
