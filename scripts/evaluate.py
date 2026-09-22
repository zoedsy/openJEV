#!/usr/bin/env python3
"""Evaluate labeled JSONL against the API or saved raw responses. Fixtures are not quality evidence."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

# Also support `python scripts/evaluate.py` before installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openjev.calibration import (EPSILON, KINDS, apply_calibration, dataset_fingerprint,
                                distribution, load_dataset, load_response_records,
                                model_identity, negative_log_likelihood,
                                target_index, validate_test_split)


def mean(values):
    return sum(values) / len(values) if values else None


def ece(pairs):
    """Equal-width 10-bin ECE; empirical descriptive statistic, not a guarantee."""
    if not pairs:
        return None
    total = 0
    for i in range(10):
        bucket = [(p, y) for p, y in pairs if min(9, int(p * 10)) == i]
        if bucket:
            total += len(bucket) / len(pairs) * abs(mean([p for p, _ in bucket]) - mean([y for _, y in bucket]))
    return total


def _point(question, answer, target):
    kind = question["type"]
    if kind not in KINDS:
        raise ValueError("Unknown question type")
    if not isinstance(answer, dict) or answer.get("type", kind) != kind:
        raise ValueError("Answer type does not match question")
    point = {"kind": kind, "unlabeled": target is None}
    # Older score artifacts only recorded the expected rubric level. Keep MAE compatibility.
    if kind == "score":
        value = answer.get("score")
        levels = len(question["criteria"])
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < levels:
            raise ValueError("Predicted score is outside its rubric")
        if value > levels - 1:
            raise ValueError("Predicted score exceeds the highest rubric level")
        if "probabilities" not in answer:
            target_index(question, target, [str(i) for i in range(levels)])
            point["probabilities_missing"] = True
            if target is not None:
                point["mae"] = abs(value - target)
            return point
    keys, probs = distribution(question, answer)
    label = target_index(question, target, keys)
    if target is None:
        return point
    if kind == "score":
        point["mae"] = abs(answer["score"] - target)
    if label is None:
        point["fractional_score_label"] = True
        return point
    point["nll"] = negative_log_likelihood(probs, label)
    if kind == "noul":
        point.update(positive=probs[1], label=label, correct=(probs[1] >= .5) == bool(label), brier=(probs[1] - label) ** 2)
    else:
        selected = keys.index(answer["choice"]) if kind == "choice" else max(range(len(probs)), key=probs.__getitem__)
        point.update(correct=selected == label, probability=probs[selected],
                     brier=sum((p - float(i == label)) ** 2 for i, p in enumerate(probs)))
    return point


def _aggregate(points):
    by_type = {}
    for kind in KINDS:
        group = [point for point in points if point["kind"] == kind]
        labeled = [point for point in group if not point["unlabeled"]]
        categorical = [point for point in labeled if "nll" in point]
        common = {"n": len(labeled), "unlabeled": len(group) - len(labeled),
                  "nll": mean([point["nll"] for point in categorical]), "nll_n": len(categorical)}
        if kind == "noul":
            common.update(accuracy_at_0_5=mean([point["correct"] for point in categorical]),
                          brier=mean([point["brier"] for point in categorical]),
                          ece_10_bins=ece([(point["positive"], point["label"]) for point in categorical]))
        else:
            common.update(accuracy=mean([point["correct"] for point in categorical]),
                          brier_sum_over_classes=mean([point["brier"] for point in categorical]),
                          top_label_ece_10_bins=ece([(point["probability"], point["correct"]) for point in categorical]))
        if kind == "score":
            common.update(mae_in_rubric_levels=mean([point["mae"] for point in labeled]),
                          mae_unit="zero-based rubric levels (not a probability or percent)",
                          missing_probability_questions=sum(point.get("probabilities_missing", False) for point in group),
                          fractional_label_questions=sum(point.get("fractional_score_label", False) for point in group))
        by_type[kind] = common
    return by_type


def summarize(rows, *, strict=True):
    """Keep legacy top-level metrics; add NLL, slices and explicit invalid/unlabeled counts.

    strict=True preserves the original caller-visible validation errors. The CLI
    uses strict=False to retain all failures alongside valid question metrics.
    """
    rows = list(rows)
    points, errors, slice_points, slice_ids = [], [], {}, {}
    for position, (item, response) in enumerate(rows):
        identifier = item.get("id", str(position))
        tags = set(item.get("slices", []))
        for tag in tags:
            slice_points.setdefault(tag, [])
            slice_ids.setdefault(tag, set()).add(identifier)
        questions = item["request"]["questions"]
        if not isinstance(response, dict):
            if strict:
                raise ValueError("Response must be an object")
            errors.append({"id": identifier, "question": None, "message": "Response must be an object"})
            response = {}
        if not isinstance(response.get("answers"), dict) or set(response["answers"]) != set(questions):
            if strict:
                raise ValueError("Answer IDs must match the request")
            errors.append({"id": identifier, "question": None, "message": "Answer IDs must match the request"})
        answers = response.get("answers", {})
        if not isinstance(answers, dict):
            answers = {}
        for key, question in questions.items():
            try:
                if key not in answers:
                    raise ValueError("Missing answer")
                if key not in item["expected"]:
                    raise ValueError("Missing expected label; use null for an explicitly unlabeled question")
                point = _point(question, answers[key], item["expected"][key])
                points.append(point)
                for tag in tags:
                    slice_points[tag].append(point)
            except (ValueError, KeyError, TypeError) as exc:
                if strict:
                    raise ValueError(f"{identifier}/{key}: {exc}") from exc
                errors.append({"id": identifier, "question": key, "type": question.get("type"), "message": str(exc)})
    kinds = _aggregate(points)
    return {"requests": len(rows), "evaluated_questions": len(points),
            "unlabeled_questions": sum(point["unlabeled"] for point in points), **kinds, "by_type": kinds,
            "slices": {tag: {"requests": len(slice_ids[tag]), "by_type": _aggregate(group)} for tag, group in sorted(slice_points.items())},
            "errors": errors, "nll_probability_floor": EPSILON,
            "note": "Metrics use supplied labels and raw label probabilities, never confidence as correctness. null labels are retained but excluded from metrics. NLL uses natural logarithms. Small or synthetic sets cannot establish calibration or equivalence to Jev."}


def build_report(items, records, *, data_source, calibration=None):
    successful = [(item, record["response"]) for item, record in zip(items, records) if isinstance(record.get("response"), dict) and not record.get("error")]
    summary = summarize(successful, strict=False)
    summary["requests"] = len(items)
    summary["completed_requests"] = len(successful)
    summary["request_errors"] = [{"id": record["id"], **record["error"]} for record in records if record.get("error")]
    summary["not_attempted_requests"] = sum(record.get("status") == "not_attempted" for record in records)
    summary["synthetic_requests"] = sum(item.get("provenance", {}).get("synthetic") is True for item in items)
    for tag in sorted({tag for item in items for tag in item.get("slices", [])}):
        selected = [(item, record) for item, record in zip(items, records) if tag in item.get("slices", [])]
        section = summary["slices"].setdefault(tag, {"by_type": _aggregate([])})
        section["requests"] = len(selected)
        section["request_errors"] = sum(bool(record.get("error")) for _, record in selected)
        selected_ids = {item["id"] for item, _ in selected}
        section["invalid_questions"] = sum(error.get("question") is not None and error["id"] in selected_ids for error in summary["errors"])
    models = []
    for _, result in successful:
        meta = result.get("meta", {})
        identity = {key: meta.get(key) for key in ("model_id", "revision", "engine", "server_revision") if meta.get(key) is not None}
        if identity not in models:
            models.append(identity)
    summary["model"] = models[0].get("model_id") if len(models) == 1 else None
    summary["model_identities"] = models
    if calibration is not None:
        paired = [(item, record) for item, record in zip(items, records) if record.get("calibrated_response") is not None]
        summary["calibration"] = {
            "artifact_fingerprint": calibration["fingerprint"], "model": calibration["model"],
            "parameters": calibration["temperatures"], "paired_requests": len(paired),
            "before": summarize([(item, record["response"]) for item, record in paired], strict=False),
            "after": summarize([(item, record["calibrated_response"]) for item, record in paired], strict=False),
            "errors": [{"id": record["id"], "message": record["calibration_error"]} for record in records if record.get("calibration_error")],
            "uncovered_questions": [{"id": record["id"], "questions": record["calibrated_response"]["meta"]["calibration"]["uncovered_question_ids"]}
                                    for _, record in paired if record["calibrated_response"]["meta"]["calibration"]["uncovered_question_ids"]],
            "note": "Before/after use exactly the same successful paired requests. Uncovered types retain raw probabilities and are explicitly listed. Held-out improvement is not guaranteed."}
    return {"format_version": 1, "dataset": {"source": str(data_source), "fingerprint": dataset_fingerprint(items), "sample_ids": [item["id"] for item in items]},
            "summary": summary, "results": records}


def _json_safe(value):
    # Malformed model probabilities must remain reviewable even when they are NaN/Inf.
    if isinstance(value, float) and not math.isfinite(value):
        return {"invalid_nonfinite_number": repr(value)}
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def write_report(path, report):
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    temporary.write_text(json.dumps(_json_safe(report), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="eval/smoke.jsonl")
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    parser.add_argument("--out", default="artifacts/evaluation.json")
    parser.add_argument("--responses", help="Evaluate an existing response artifact without making API requests")
    parser.add_argument("--calibration", help="Offline calibration JSON fitted on a disjoint calibration split")
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args(argv)
    try:
        items = load_dataset(args.data)
        saved = load_response_records(args.responses, items) if args.responses else None
        calibration = json.loads(Path(args.calibration).read_text()) if args.calibration else None
        if calibration is not None:
            validate_test_split(calibration, items)
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be finite and positive")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    headers = {"Content-Type": "application/json"}
    if os.getenv("OPENJEV_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["OPENJEV_API_KEY"]
    opener = build_opener(ProxyHandler({}))
    records = [{**item, "status": "not_attempted"} for item in items]
    identity = None
    interrupted = False
    for item, record in zip(items, records):
        try:
            if saved is not None:
                previous = saved[item["id"]]
                if previous.get("error"):
                    record["response"] = previous.get("response")
                    raise ValueError("Saved request failure: " + str(previous["error"]))
                result = previous.get("response")
            else:
                request = Request(args.url.rstrip("/") + "/v1/systemone", data=json.dumps(item["request"]).encode(), headers=headers)
                with opener.open(request, timeout=args.timeout) as response:
                    result = json.load(response)
            record["response"] = result
            if not isinstance(result, dict):
                raise ValueError("Response must be an object")
            if not isinstance(result.get("meta", {}), dict):
                raise ValueError("Response meta must be an object")
            if result.get("meta", {}).get("model_id") and result.get("meta", {}).get("revision"):
                current = model_identity(result)
                if identity is not None and current != identity:
                    raise ValueError("Model identity/revision changed during evaluation")
                identity = current
            record["status"] = "completed"
            answer_errors = summarize([(item, result)], strict=False)["errors"]
            if answer_errors:
                record["status"] = "invalid_answers"
                record["answer_errors"] = answer_errors
            if calibration is not None:
                try:
                    # Validate raw questions before pairing to keep comparisons meaningful.
                    summarize([(item, result)])
                    record["calibrated_response"] = apply_calibration(result, item["request"]["questions"], calibration)
                except (ValueError, KeyError, TypeError) as exc:
                    record["calibration_error"] = str(exc)
        except KeyboardInterrupt:
            record["status"] = "interrupted"
            record["error"] = {"kind": "interrupted", "message": "Interrupted before a complete response"}
            interrupted = True
        except (OSError, ValueError, KeyError, TypeError) as exc:
            record["status"] = "failed"
            # Preserve the original response in the artifact, without dumping request data into console errors.
            record["error"] = {"kind": type(exc).__name__, "message": str(exc)}
            if isinstance(exc, HTTPError):
                record["error"]["http_status"] = exc.code
        report = build_report(items, records, data_source=args.data, calibration=calibration)
        write_report(args.out, report)
        if interrupted:
            break
    report = build_report(items, records, data_source=args.data, calibration=calibration)
    write_report(args.out, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, allow_nan=False))
    if interrupted:
        return 130
    errors = report["summary"]["errors"] or report["summary"]["request_errors"]
    if calibration is not None:
        errors = errors or report["summary"]["calibration"]["errors"]
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
