from copy import deepcopy
import json
import math

import pytest

from openjev.calibration import (apply_calibration, distribution, fit_calibration,
                                fit_temperature, load_dataset, load_response_records,
                                negative_log_likelihood, temperature_scale,
                                validate_artifact, validate_test_split)
from scripts.calibrate import main as calibrate_main
from scripts.evaluate import main as evaluate_main


def row(identifier, label=True, *, split="calibration"):
    item = {"id": identifier, "split": split, "request": {"state": identifier, "questions": {"n": {"type": "noul", "instructions": "An explicit claim is present."}}}, "expected": {"n": label}}
    response = {"answers": {"n": {"noul": .99}}, "meta": {"model_id": "fixture-model", "revision": "fixture-revision", "engine": "fixture", "calibrated": False}}
    return item, response


def artifact():
    return fit_calibration([row("cal-a", True), row("cal-b", False)], source="unit-test-fixture", min_samples=2)


def test_temperature_softens_without_changing_order_and_handles_exact_zeros():
    p = temperature_scale([0, .1, .9], 2)
    assert all(math.isfinite(value) and value > 0 for value in p)
    assert sum(p) == pytest.approx(1)
    assert p[2] > p[1] > p[0]
    assert p[2] < .9
    assert temperature_scale([.2, .8], 1) == pytest.approx([.2, .8])
    with pytest.raises(ValueError, match="positive"):
        temperature_scale([.2, .8], 0)


def test_fitting_reduces_training_nll_for_overconfident_errors():
    samples = [([.99, .01], 0), ([.99, .01], 1), ([.01, .99], 0), ([.01, .99], 1)]
    temperature = fit_temperature(samples)
    before = sum(negative_log_likelihood(p, y) for p, y in samples)
    after = sum(negative_log_likelihood(temperature_scale(p, temperature), y) for p, y in samples)
    assert temperature > 1
    assert after < before
    # This verifies the optimizer on constructed probabilities, not model quality.


def test_version_fingerprint_and_type_coverage_are_preserved():
    fitted = artifact()
    assert validate_artifact(fitted) is fitted
    assert fitted["format_version"] == 1
    assert fitted["calibration_data"]["sample_ids"] == ["cal-a", "cal-b"]
    assert fitted["coverage"]["choice"]["fitted"] is False
    broken = deepcopy(fitted)
    broken["temperatures"]["noul"] = 3
    with pytest.raises(ValueError, match="fingerprint"):
        validate_artifact(broken)


def test_disjoint_split_ids_contents_and_model_identity_are_enforced():
    fitted = artifact()
    test_item, test_result = row("test-a", split="test")
    validate_test_split(fitted, [test_item])
    with pytest.raises(ValueError, match="split=test"):
        validate_test_split(fitted, [row("not-test")[0]])
    duplicate = deepcopy(test_item)
    duplicate["id"] = "cal-a"
    with pytest.raises(ValueError, match="IDs overlap"):
        validate_test_split(fitted, [duplicate])
    duplicate["id"] = "new-id"
    duplicate["request"] = row("cal-a")[0]["request"]
    with pytest.raises(ValueError, match="contents overlap"):
        validate_test_split(fitted, [duplicate])
    test_result["meta"]["revision"] = "different-revision"
    with pytest.raises(ValueError, match="identity/revision"):
        apply_calibration(test_result, test_item["request"]["questions"], fitted)


def test_fit_rejects_mixed_models_non_calibration_split_and_calibrated_input():
    first, second = row("a"), row("b")
    second[1]["meta"]["revision"] = "other"
    with pytest.raises(ValueError, match="different model"):
        fit_calibration([first, second], source="test", min_samples=2)
    with pytest.raises(ValueError, match="split=calibration"):
        fit_calibration([row("a", split="test"), row("b")], source="test", min_samples=2)
    second = row("b")
    second[1]["meta"]["calibrated"] = True
    with pytest.raises(ValueError, match="raw uncalibrated"):
        fit_calibration([first, second], source="test", min_samples=2)


def test_apply_keeps_raw_input_untouched_and_reports_uncovered_questions():
    fitted = artifact()
    item, result = row("test-a", split="test")
    item["request"]["questions"]["c"] = {"type": "choice", "criteria": {"yes": "Yes", "no": "No"}}
    result["answers"]["c"] = {"choice": "yes", "probabilities": {"yes": .8, "no": .2}}
    original = deepcopy(result)
    adjusted = apply_calibration(result, item["request"]["questions"], fitted)
    assert result == original
    assert .5 < adjusted["answers"]["n"]["noul"] < .99
    assert adjusted["answers"]["c"] == original["answers"]["c"]
    assert adjusted["meta"]["calibrated"] is False
    assert adjusted["meta"]["calibration"]["uncovered_question_ids"] == ["c"]
    with pytest.raises(ValueError, match="already calibrated"):
        apply_calibration(adjusted, item["request"]["questions"], fitted)


@pytest.mark.parametrize("probabilities", [{"a": .9, "b": .2}, {"a": float("nan"), "b": .1}, {"a": True, "b": 0}, {"a": -.1, "b": 1.1}])
def test_invalid_raw_probabilities_are_rejected(probabilities):
    with pytest.raises(ValueError):
        distribution({"type": "choice", "criteria": {"a": "A", "b": "B"}}, {"choice": "a", "probabilities": probabilities})


def test_score_calibration_recomputes_expected_rubric_level():
    rows = []
    for index, label in enumerate([0, 2]):
        item, result = row("score-" + str(index))
        item["request"]["questions"] = {"s": {"type": "score", "criteria": ["low", "mid", "high"]}}
        item["expected"] = {"s": label}
        result["answers"] = {"s": {"score": 1.7, "probabilities": {"0": .1, "1": .1, "2": .8}, "confidence": .4}}
        rows.append((item, result))
    fitted = fit_calibration(rows, source="score-fixture", min_samples=2)
    item, result = rows[0]
    adjusted = apply_calibration(result, item["request"]["questions"], fitted)
    probs = adjusted["answers"]["s"]["probabilities"]
    assert adjusted["answers"]["s"]["score"] == pytest.approx(sum(int(key) * p for key, p in probs.items()))
    assert adjusted["answers"]["s"]["score"] < 1.7


def test_duplicate_dataset_ids_and_record_content_mismatch_are_rejected(tmp_path):
    item, result = row("same")
    data = tmp_path / "data.jsonl"
    data.write_text(json.dumps(item) + "\n" + json.dumps(item) + "\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(data)
    saved = tmp_path / "responses.json"
    saved.write_text(json.dumps({"results": [{"id": item["id"], "request": {"state": "wrong"}, "response": result}]}))
    with pytest.raises(ValueError, match="request does not match"):
        load_response_records(saved, [item])


def test_offline_cli_end_to_end_uses_heldout_labels_only_for_evaluation(tmp_path, capsys):
    calibration_rows = [row("cal-a", True), row("cal-b", False)]
    test_rows = [row("test-a", False, split="test"), row("test-b", True, split="test")]
    paths = {}
    for split, rows in [("calibration", calibration_rows), ("test", test_rows)]:
        data = tmp_path / (split + ".jsonl")
        responses = tmp_path / (split + ".json")
        data.write_text("".join(json.dumps(item) + "\n" for item, _ in rows))
        responses.write_text(json.dumps({"results": [{"id": item["id"], "response": response} for item, response in rows]}))
        paths[split] = (str(data), str(responses))
    parameters = tmp_path / "temperature.json"
    assert calibrate_main(["--data", paths["calibration"][0], "--responses", paths["calibration"][1], "--out", str(parameters), "--min-samples", "2"]) == 0
    before_file = parameters.read_text()
    out = tmp_path / "report.json"
    assert evaluate_main(["--data", paths["test"][0], "--responses", paths["test"][1], "--calibration", str(parameters), "--out", str(out)]) == 0
    report = json.loads(out.read_text())
    comparison = report["summary"]["calibration"]
    assert comparison["paired_requests"] == 2
    assert comparison["after"]["noul"]["nll"] < comparison["before"]["noul"]["nll"]
    assert report["results"][0]["response"]["answers"]["n"]["noul"] == .99
    assert parameters.read_text() == before_file
    assert "test-a" not in json.loads(before_file)["calibration_data"]["sample_ids"]
    capsys.readouterr()


def test_calibration_cli_does_not_silently_drop_failed_predictions(tmp_path):
    items = [row("a")[0], row("b")[0]]
    data, responses = tmp_path / "cal.jsonl", tmp_path / "raw.json"
    data.write_text("".join(json.dumps(item) + "\n" for item in items))
    responses.write_text(json.dumps({"results": [{"id": "a", "response": row("a")[1]}, {"id": "b", "error": {"message": "failed"}}]}))
    with pytest.raises(SystemExit) as exc:
        calibrate_main(["--data", str(data), "--responses", str(responses), "--min-samples", "2"])
    assert exc.value.code == 2


def test_grouped_conversation_variants_cannot_cross_calibration_and_test():
    rows = [row("cal-a"), row("cal-b", False)]
    rows[0][0]["group_id"] = "same-conversation"
    fitted = fit_calibration(rows, source="unit-test-fixture", min_samples=2)
    item, _ = row("different-ticket-version", split="test")
    item["group_id"] = "same-conversation"
    with pytest.raises(ValueError, match="group IDs overlap"):
        validate_test_split(fitted, [item])
    assert fitted["calibration_data"]["prediction_fingerprint"]


def test_cli_reports_revision_mismatch_without_losing_raw_response(tmp_path, capsys):
    fitted = artifact()
    item, result = row("test-new-model", split="test")
    result["meta"]["revision"] = "new-checkpoint"
    data, raw, params, out = [tmp_path / name for name in ("test.jsonl", "raw.json", "params.json", "out.json")]
    data.write_text(json.dumps(item) + "\n")
    raw.write_text(json.dumps({"results": [{"id": item["id"], "response": result}]}))
    params.write_text(json.dumps(fitted))
    assert evaluate_main(["--data", str(data), "--responses", str(raw), "--calibration", str(params), "--out", str(out)]) == 1
    report = json.loads(out.read_text())
    assert report["results"][0]["response"] == result
    assert "identity/revision" in report["results"][0]["calibration_error"]
    assert report["summary"]["calibration"]["paired_requests"] == 0
    capsys.readouterr()


def test_inconsistent_decision_and_distribution_cannot_improve_metrics_by_relabeling():
    with pytest.raises(ValueError, match="highest-probability"):
        distribution({"type": "choice", "criteria": {"a": "A", "b": "B"}}, {"choice": "b", "probabilities": {"a": .9, "b": .1}})
    with pytest.raises(ValueError, match="expected rubric level"):
        distribution({"type": "score", "criteria": ["low", "high"]}, {"score": .8, "probabilities": {"0": .8, "1": .2}})
