"""Optional adapter for the existing Apache-2.0 Kev local server.

No upstream source is vendored. Uses Kev's documented /v1/systemone contract.
Requests remain on the local machine; arbitrary remote URLs are not accepted.
"""

import json
import math
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise KevUnavailable("Kev redirects are not followed; requests must remain on loopback")


class KevUnavailable(RuntimeError):
    pass


class KevBackend:
    def __init__(self, base_url="http://127.0.0.1:8009"):
        parsed = urlparse(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("OPENJEV_KEV_URL must be a loopback HTTP origin, e.g. http://127.0.0.1:8009")
        self.base_url = base_url.rstrip("/")
        self.status = "loading"
        self.error = None
        self.model_id = "jaredpalmer/kev"
        self.revision = "reported by upstream"

    def _request(self, path, body=None):
        request = Request(self.base_url + path,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect).open(request, timeout=180 if body is not None else 5) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise KevUnavailable("Cannot reach the local Kev server. Start Kev on port 8009; see docs/backends.md.") from exc

    def load(self):
        try:
            models = self._request("/v1/models")["models"]
            self.model_id = models[0].get("run", "jaredpalmer/kev")
            self.status, self.error = "ready", None
        except Exception as exc:
            self.status, self.error = "error", str(exc)
            raise

    def evaluate(self, request):
        started = time.perf_counter()
        payload = request.model_dump(exclude_none=True)
        payload["model"] = "kev-latest"
        result = self._request("/v1/systemone", payload)
        answers = result.get("answers", {})
        if set(answers) != set(request.questions):
            raise KevUnavailable("Kev returned an unexpected set of question IDs")
        for key, question in request.questions.items():
            answer = answers[key]
            if answer.get("type") != question.type:
                raise KevUnavailable("Kev returned an unexpected answer type")
            if question.type == "noul":
                values = [answer.get("noul")]
            else:
                expected = set(question.criteria) if question.type == "choice" else {str(i) for i in range(len(question.criteria))}
                probabilities = answer.get("probabilities", {})
                if set(probabilities) != expected:
                    raise KevUnavailable("Kev returned unexpected probability keys")
                values = list(probabilities.values()) + [answer.get("confidence")]
                if question.type == "choice" and answer.get("choice") not in expected:
                    raise KevUnavailable("Kev selected an unknown option")
                if question.type == "score":
                    score = answer.get("score")
                    if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= len(expected)-1:
                        raise KevUnavailable("Kev returned an invalid score")
            if any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise KevUnavailable("Kev returned invalid probabilities")
        result["meta"] = {
            "engine": "kev", "model_id": self.model_id, "revision": self.revision,
            "latency_ms": round((time.perf_counter()-started)*1000, 1),
            "evaluations": sum(len(q.criteria) if q.type != "noul" else 2 for q in request.questions.values()),
            "calibrated": False,
            "confidence_method": "upstream Kev formula; see upstream model card",
            "note": "Kev rounds probabilities to two decimals. Calibration outside its training distribution is not established.",
        }
        return result
