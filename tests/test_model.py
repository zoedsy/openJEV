"""Opt-in checks using REAL pinned weights, never stubs or hard-coded answers."""

import os

import pytest

from openjev.config import Settings
from openjev.engine import LocalNLI, evaluate
from openjev.schema import SystemOneRequest

pytestmark = [pytest.mark.model, pytest.mark.skipif(os.getenv("OPENJEV_TEST_MODEL") != "1", reason="Set OPENJEV_TEST_MODEL=1 after downloading weights")]


@pytest.fixture(scope="module")
def model():
    engine = LocalNLI(Settings.from_env())
    engine.load()
    return engine


def test_real_support_contradiction_and_batch_isolation(model):
    questions = {
        "true": {"type":"noul","instructions":"The person lives in Berlin."},
        "false": {"type":"noul","instructions":"The person lives in London."},
    }
    request = SystemOneRequest(state="I live in Berlin, Germany.", questions=questions)
    result = evaluate(request, model)
    assert result["answers"]["true"]["noul"] > .7
    assert result["answers"]["false"]["noul"] < .3
    separate = evaluate(SystemOneRequest(state=request.state, questions={"renamed":questions["true"]}),model)
    assert result["answers"]["true"]["noul"] == pytest.approx(separate["answers"]["renamed"]["noul"], abs=1e-5)


def test_real_chinese_and_option_permutation(model):
    criteria = {"refund":"顾客希望退货退款。", "buy":"顾客希望购买新产品。", "delivery":"顾客询问快递配送进度。"}
    def ask(options):
        return evaluate(SystemOneRequest(state="耳机坏了，我想退货退款。", questions={"q":{"type":"choice", "instructions":"顾客想做什么？", "criteria":options}}), model)["answers"]["q"]
    forward, reverse = ask(criteria), ask(dict(reversed(list(criteria.items()))))
    assert forward["choice"] == "refund"
    assert forward["probabilities"] == pytest.approx(reverse["probabilities"], abs=1e-5)
    assert sum(forward["probabilities"].values()) == pytest.approx(1)
