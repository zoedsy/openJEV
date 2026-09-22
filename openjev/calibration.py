"""Offline temperature scaling of raw label probabilities; never enabled by the API.

A fitted temperature changes probability sharpness, not categorical rankings.
Synthetic fixtures exercise this pipeline and are not calibration evidence.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

FORMAT_VERSION = 1
EPSILON = 1e-12
KINDS = ("choice", "noul", "score")


def fingerprint(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def dataset_fingerprint(items):
    return fingerprint(sorted(items, key=lambda item: item["id"]))


def load_dataset(path):
    items = []
    seen = set()
    for line_number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            # A dataset fingerprint and API JSON must never depend on NaN/Infinity.
            json.dumps(item, allow_nan=False)
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                raise ValueError("Every sample needs a nonempty string id")
            if item["id"] in seen:
                raise ValueError("Duplicate sample id: " + item["id"])
            if not isinstance(item.get("request"), dict) or not isinstance(item.get("expected"), dict):
                raise ValueError("request and expected must be objects")
            questions = item["request"].get("questions")
            if not isinstance(questions, dict) or not questions:
                raise ValueError("request.questions must be a nonempty object")
            if any(not isinstance(question, dict) or question.get("type") not in KINDS for question in questions.values()):
                raise ValueError("Every question must have a recognized type")
            if not isinstance(item.get("provenance", {}), dict):
                raise ValueError("provenance must be an object")
            if set(item["expected"]) != set(questions):
                raise ValueError("Every question needs exactly one expected label (null is explicitly unlabeled)")
            if "group_id" in item and (not isinstance(item["group_id"], str) or not item["group_id"]):
                raise ValueError("group_id must be a nonempty string when supplied")
            if not isinstance(item.get("slices", []), list) or any(not isinstance(v, str) for v in item.get("slices", [])):
                raise ValueError("slices must be a list of strings")
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
        items.append(item)
        seen.add(item["id"])
    if not items:
        raise ValueError("Evaluation data is empty")
    return items


def model_identity(response):
    meta = response.get("meta", {})
    if not isinstance(meta, dict) or any(not isinstance(meta.get(key), str) or not meta[key] for key in ("model_id", "revision")):
        raise ValueError("Calibration requires model_id and revision in response.meta")
    return {key: meta[key] for key in ("model_id", "revision", "engine", "server_revision") if meta.get(key) is not None}


def probability(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Probabilities must be finite numbers in [0, 1]")
    return float(value)


def distribution(question, answer):
    kind = question["type"]
    if not isinstance(answer, dict) or answer.get("type", kind) != kind:
        raise ValueError("Answer type does not match question")
    if kind == "noul":
        positive = probability(answer["noul"])
        return ["false", "true"], [1 - positive, positive]
    if kind not in ("choice", "score"):
        raise ValueError("Unknown question type: " + str(kind))
    values = answer.get("probabilities")
    if not isinstance(values, dict) or len(values) < 2:
        raise ValueError("Categorical answers require raw probabilities for at least two labels")
    keys = list(values)
    criteria = question.get("criteria")
    expected = set(criteria) if kind == "choice" and criteria is not None else ({str(i) for i in range(len(criteria))} if kind == "score" else set(keys))
    if set(keys) != expected:
        raise ValueError("Probability keys do not match the question criteria")
    probs = [probability(values[key]) for key in keys]
    if not math.isclose(sum(probs), 1, rel_tol=0, abs_tol=1e-5):
        raise ValueError("Probabilities do not sum to one")
    if kind == "choice":
        if answer.get("choice") not in keys:
            raise ValueError("Selected choice is absent from probabilities")
        if probs[keys.index(answer["choice"])] + 1e-8 < max(probs):
            raise ValueError("Selected choice is not a highest-probability candidate")
    if kind == "score":
        score = answer.get("score")
        expected = sum(int(key) * p for key, p in zip(keys, probs))
        if type(score) not in (int, float) or not math.isfinite(score) or not math.isclose(score, expected, rel_tol=0, abs_tol=1e-5):
            raise ValueError("Score does not match the expected rubric level from its probabilities")
    return keys, probs


def target_index(question, target, keys):
    if target is None:
        return None
    kind = question["type"]
    if kind == "noul":
        if type(target) not in (bool, int) or target not in (0, 1):
            raise ValueError("Noul targets must be binary outcomes or null for unlabeled")
        return int(target)
    if kind == "choice":
        if not isinstance(target, str) or target not in keys:
            raise ValueError("Choice target is absent from candidates")
        return keys.index(target)
    if type(target) not in (int, float) or not math.isfinite(target) or not 0 <= target <= len(question["criteria"]) - 1:
        raise ValueError("Score target is outside its rubric")
    # Fractional human-averaged rubric labels support MAE, but are not a categorical event.
    return keys.index(str(int(target))) if float(target).is_integer() else None


def temperature_scale(probs, temperature):
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Temperature must be finite and positive")
    checked = [probability(p) for p in probs]
    if len(checked) < 2 or not math.isclose(sum(checked), 1, abs_tol=1e-5, rel_tol=0):
        raise ValueError("Expected a normalized categorical probability vector")
    logs = [math.log(max(EPSILON, p)) / temperature for p in checked]
    shift = max(logs)
    weights = [math.exp(value - shift) for value in logs]
    total = sum(weights)
    return [weight / total for weight in weights]


def negative_log_likelihood(probs, label):
    return -math.log(max(EPSILON, probs[label]))


def fit_temperature(samples, lower=0.05, upper=20.0):
    """Minimize categorical NLL in log-temperature using bounded golden-section search."""
    if not samples:
        raise ValueError("No labeled probability samples to fit")
    if not 0 < lower < 1 < upper:
        raise ValueError("Temperature bounds must contain 1")
    def loss(log_temperature):
        return sum(negative_log_likelihood(temperature_scale(p, math.exp(log_temperature)), y) for p, y in samples) / len(samples)
    left, right = math.log(lower), math.log(upper)
    ratio = (math.sqrt(5) - 1) / 2
    a, b = right - ratio * (right - left), left + ratio * (right - left)
    fa, fb = loss(a), loss(b)
    for _ in range(96):
        if fa < fb:
            right, b, fb = b, a, fa
            a = right - ratio * (right - left)
            fa = loss(a)
        else:
            left, a, fa = a, b, fb
            b = left + ratio * (right - left)
            fb = loss(b)
    best = min((math.log(lower), math.log(upper), (left + right) / 2, 0.0), key=loss)
    return math.exp(best)


def load_response_records(path, items):
    """Read current or legacy {results: [{id, response}]} evaluation artifacts."""
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError("Response artifact must be an object")
    entries = payload.get("results")
    if not isinstance(entries, list):
        raise ValueError("Response artifact must contain a results list")
    records = {}
    expected = {item["id"] for item in items}
    for record in entries:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("Every response record needs a string id")
        identifier = record.get("id")
        if identifier in records:
            raise ValueError("Duplicate response id: " + str(identifier))
        records[identifier] = record
    if set(records) != expected:
        raise ValueError("Response IDs must match the supplied dataset exactly")
    for item in items:
        record = records[item["id"]]
        if "request" in record and fingerprint(record["request"]) != fingerprint(item["request"]):
            raise ValueError("Recorded request does not match dataset for " + item["id"])
        if "expected" in record and record["expected"] != item["expected"]:
            raise ValueError("Recorded labels do not match dataset for " + item["id"])
    return records


def fit_calibration(rows, *, source, min_samples=20):
    """Fit one temperature per type from an explicit calibration split only."""
    if type(min_samples) is not int or min_samples < 2:
        raise ValueError("min_samples must be at least 2")
    items = [item for item, _ in rows]
    ids = [item["id"] for item in items]
    if not items or len(set(ids)) != len(ids):
        raise ValueError("Calibration samples must have unique IDs")
    if any(item.get("split") != "calibration" for item in items):
        raise ValueError("Fitting requires every sample to declare split=calibration")
    grouped = {kind: [] for kind in KINDS}
    skipped = []
    identity = None
    for item, response in rows:
        current = model_identity(response)
        if identity is not None and current != identity:
            raise ValueError("Cannot fit across different model identities/revisions")
        identity = current
        if response.get("meta", {}).get("calibration") or response.get("meta", {}).get("calibrated"):
            raise ValueError("Fit from raw uncalibrated probabilities, not previously calibrated responses")
        if set(response.get("answers", {})) != set(item["request"]["questions"]):
            raise ValueError("Answer IDs must match the request")
        for key, question in item["request"]["questions"].items():
            keys, probs = distribution(question, response["answers"][key])
            target = item["expected"][key]
            label = target_index(question, target, keys)
            if label is None:
                skipped.append({"id": item["id"], "question": key, "reason": "unlabeled" if target is None else "fractional_score_label"})
            else:
                grouped[question["type"]].append((probs, label))
    temperatures, coverage = {}, {}
    for kind, samples in grouped.items():
        if len(samples) < min_samples:
            coverage[kind] = {"fitted": False, "n": len(samples), "reason": f"fewer_than_{min_samples}_labeled_questions"}
            continue
        fitted = fit_temperature(samples)
        temperatures[kind] = fitted
        coverage[kind] = {"fitted": True, "n": len(samples),
                          "calibration_nll_before": sum(negative_log_likelihood(p, y) for p, y in samples) / len(samples),
                          "calibration_nll_after": sum(negative_log_likelihood(temperature_scale(p, fitted), y) for p, y in samples) / len(samples),
                          "temperature_at_bound": math.isclose(fitted, .05, abs_tol=1e-5) or math.isclose(fitted, 20, abs_tol=1e-5)}
    if not temperatures:
        raise ValueError("No type has enough labeled questions to fit; collect data or explicitly lower --min-samples for a pipeline-only smoke test")
    artifact = {"format_version": FORMAT_VERSION, "method": "temperature_scaling_by_type", "created_at": datetime.now(timezone.utc).isoformat(),
                "model": identity, "temperatures": temperatures, "coverage": coverage,
                "fitting": {"objective": "categorical_negative_log_likelihood", "probability_floor": EPSILON,
                            "temperature_bounds": [.05, 20.0], "min_samples_per_type": min_samples},
                "calibration_data": {"source": str(source), "fingerprint": dataset_fingerprint(items), "sample_ids": sorted(ids),
                                     "prediction_fingerprint": fingerprint([{"id": item["id"], "response": response} for item, response in rows]),
                                     "group_ids": sorted({item["group_id"] for item in items if item.get("group_id")}),
                                     "request_fingerprints": sorted({fingerprint(item["request"]) for item in items}),
                                     "synthetic_samples": sum(item.get("provenance", {}).get("synthetic") is True for item in items)},
                "skipped_labels": skipped,
                "note": "Offline parameters only. Calibration-split loss is fitting diagnostics, not independent quality evidence. Evaluate an untouched test set; temperatures may worsen its metrics."}
    artifact["fingerprint"] = fingerprint(artifact)
    return artifact


def validate_artifact(artifact):
    if not isinstance(artifact, dict) or artifact.get("format_version") != FORMAT_VERSION or artifact.get("method") != "temperature_scaling_by_type":
        raise ValueError("Unsupported calibration file version or method")
    unsigned = {key: value for key, value in artifact.items() if key != "fingerprint"}
    if artifact.get("fingerprint") != fingerprint(unsigned):
        raise ValueError("Calibration file fingerprint does not match its contents")
    model_identity({"meta": artifact.get("model")})
    temperatures = artifact.get("temperatures", {})
    if not temperatures or set(temperatures) - set(KINDS):
        raise ValueError("Calibration file has invalid temperature types")
    for value in temperatures.values():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Calibration file has invalid temperature")
    provenance = artifact.get("calibration_data", {})
    if not provenance.get("fingerprint") or not isinstance(provenance.get("sample_ids"), list) or not isinstance(provenance.get("request_fingerprints"), list):
        raise ValueError("Calibration file is missing dataset provenance")
    return artifact


def validate_test_split(artifact, items):
    validate_artifact(artifact)
    if any(item.get("split") != "test" for item in items):
        raise ValueError("Evaluation with calibration requires every sample to declare split=test")
    known_ids = set(artifact["calibration_data"]["sample_ids"])
    overlap = known_ids.intersection(item["id"] for item in items)
    if overlap:
        raise ValueError("Calibration/test sample IDs overlap: " + ", ".join(sorted(overlap)))
    known_groups = set(artifact["calibration_data"].get("group_ids", []))
    overlap_groups = known_groups.intersection(item["group_id"] for item in items if item.get("group_id"))
    if overlap_groups:
        raise ValueError("Calibration/test group IDs overlap: " + ", ".join(sorted(overlap_groups)))
    requests = set(artifact["calibration_data"]["request_fingerprints"])
    if any(fingerprint(item["request"]) in requests for item in items):
        raise ValueError("Calibration/test request contents overlap despite different IDs")


def apply_calibration(response, questions, artifact):
    validate_artifact(artifact)
    if model_identity(response) != artifact["model"]:
        raise ValueError("Calibration model identity/revision does not match this response")
    if response.get("meta", {}).get("calibration") or response.get("meta", {}).get("calibrated"):
        raise ValueError("Response is already calibrated; use the original raw response")
    if set(response.get("answers", {})) != set(questions):
        raise ValueError("Answer IDs must match the request")
    result = deepcopy(response)
    transformed, uncovered = [], []
    for key, question in questions.items():
        kind = question["type"]
        temperature = artifact["temperatures"].get(kind)
        if temperature is None:
            uncovered.append(key)
            continue
        answer = result["answers"][key]
        keys, probs = distribution(question, answer)
        calibrated = temperature_scale(probs, temperature)
        if kind == "noul":
            answer["noul"] = calibrated[1]
        else:
            answer["probabilities"] = dict(zip(keys, calibrated))
            if kind == "choice":
                answer["choice"] = keys[max(range(len(keys)), key=calibrated.__getitem__)]
            else:
                answer["score"] = sum(int(key) * p for key, p in zip(keys, calibrated))
            answer["confidence"] = max(0.0, min(1.0, 1 + sum(p * math.log(p) for p in calibrated if p) / math.log(len(keys))))
        transformed.append(key)
    result["meta"]["calibrated"] = bool(transformed) and not uncovered
    result["meta"]["calibration"] = {"method": artifact["method"], "artifact_fingerprint": artifact["fingerprint"],
                                      "transformed_question_ids": transformed, "uncovered_question_ids": uncovered,
                                      "scope": "offline_evaluation_only"}
    return result
