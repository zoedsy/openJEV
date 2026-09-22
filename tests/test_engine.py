"""Contract, math, and isolation tests; no model download required."""

import math

import pytest
from pydantic import ValidationError

from openjev.engine import Prediction, confidence, evaluate, make_pairs, softmax
from openjev.schema import SystemOneRequest


class FixedScorer:
    model_id = "test-only"
    revision = "test"

    def __init__(self, logits):
        self.logits = logits

    def predict(self, pairs):
        assert len(pairs) == len(self.logits)
        return Prediction(self.logits, input_tokens=42)


def request(questions, state="Context"):
    return SystemOneRequest(state=state, questions=questions)


def test_mixed_response_math_and_shapes():
    body = request({
        "route": {"type": "choice", "instructions": "Route it", "criteria": {"a": "A", "b": "B"}},
        "quality": {"type": "score", "instructions": "Quality", "criteria": ["low", "medium", "high"]},
        "known": {"type": "noul", "instructions": "The claim is supported"},
    })
    logits = [(0, 0, 0), (math.log(3), 0, 0),
              (math.log(.2), 0, 0), (math.log(.3), 0, 0), (math.log(.5), 0, 0),
              (math.log(.6), math.log(.2), math.log(.2))]
    result = evaluate(body, FixedScorer(logits))
    route, quality, known = (result["answers"][key] for key in ("route", "quality", "known"))
    assert route["choice"] == "b"
    assert route["probabilities"] == pytest.approx({"a": .25, "b": .75})
    assert quality["score"] == pytest.approx(1.3)
    assert quality["legend"] == {"0": "low", "1": "medium", "2": "high"}
    assert known == {"type": "noul", "noul": pytest.approx(.7)}
    assert "confidence" not in known
    assert result["usage"] == {"input_tokens": 42, "output_tokens": 0}
    assert result["meta"]["calibrated"] is False


def test_entropy_extremes_and_stability():
    assert confidence([.5, .5]) == pytest.approx(0)
    assert confidence([1, 0]) == pytest.approx(1)
    assert 0 < confidence([.9, .1]) < 1
    assert softmax([10000, 10000]) == [.5, .5]
    assert sum(softmax([-10000, 0, 10000])) == pytest.approx(1)


def test_unknown_noul_does_not_become_a_confident_no():
    body = request({"x": {"type": "noul", "instructions": "Unknown claim"}})
    answer = evaluate(body, FixedScorer([(0, 30, 0)]))["answers"]["x"]
    assert answer["noul"] == pytest.approx(.5)


def test_explicit_noul_criteria_are_respected():
    body = request({"x": {"type": "noul", "instructions": "Urgent?", "criteria": {"true": "today", "false": "next year"}}})
    pairs, _ = make_pairs(body)
    assert pairs == [("Context", "Urgent?\ntoday"), ("Context", "Urgent?\nnext year")]
    assert evaluate(body, FixedScorer([(math.log(9), 0, 0), (0, 0, 0)]))["answers"]["x"]["noul"] == pytest.approx(.9)


def test_question_ids_siblings_and_score_positions_are_not_model_context():
    q = {"type": "score", "instructions": "Quality", "criteria": ["poor", "good"]}
    single = request({"arbitrary_secret_id": q})
    mixed = request({"renamed": q, "secret": {"type": "noul", "instructions": "SIBLING SECRET"}})
    first_pairs, _ = make_pairs(single)
    other_pairs, _ = make_pairs(mixed)
    assert first_pairs == other_pairs[:2]
    assert first_pairs == [("Context", "Quality\npoor"), ("Context", "Quality\ngood")]


def test_structured_descriptions_preserved_and_null_option_supported():
    level = {"description": "good", "examples": ["works"]}
    body = request({"s": {"type": "score", "instructions": {"question": "rate"}, "criteria": ["bad", level]},
                    "c": {"type": "choice", "instructions": "pick", "criteria": {"yes": None, "no": "no"}}}, state={"text": "你好"})
    answer = evaluate(body, FixedScorer([(0, 0, 0)] * 4))["answers"]["s"]
    assert answer["legend"]["1"] == level
    pairs, _ = make_pairs(body)
    assert "你好" in pairs[0][0]
    assert pairs[2][1] == "pick\nyes"


@pytest.mark.parametrize("questions", [
    {},
    {"x": {"type": "made-up", "instructions": "bad"}},
    {"x": {"type": "noul", "instructions": " "}},
    {"x": {"type": "choice", "instructions": "x", "criteria": {"only": None}}},
    {"x": {"type": "score", "instructions": "x", "criteria": ["only"]}},
    {"x": {"type": "score", "instructions": "x", "criteria": ["x"] * 11}},
    {"x": {"type": "noul", "instructions": "x", "criteria": {"bad": "value"}}},
    {"x": {"type": "choice", "instructions": "x", "criteria": {"": None, "ok": None}}},
    {"x": {"type": "noul", "instructions": "x", "unexpected": 1}},
])
def test_bad_questions_are_rejected(questions):
    with pytest.raises(ValidationError):
        request(questions)


def test_workload_limit():
    choice = {"type": "choice", "instructions": "pick", "criteria": {str(i): None for i in range(200)}}
    with pytest.raises(ValidationError, match="256"):
        request({"one": choice, "two": choice})


@pytest.mark.parametrize("state", [None, "", " ", 123, True, "x" * 60001])
def test_invalid_states(state):
    with pytest.raises(ValidationError):
        request({"n": {"type": "noul", "instructions": "claim"}}, state)


def test_nonfinite_json_state_is_rejected():
    with pytest.raises(ValidationError):
        request({"n": {"type": "noul", "instructions": "claim"}}, {"value": float("nan")})
