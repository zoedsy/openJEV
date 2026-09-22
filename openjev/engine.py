"""Non-generative NLI inference and explicit typed-decision mathematics.

Question IDs and Score indices never enter the model. Candidate pairs are
independent, including when micro-batched. The logits are uncalibrated.
"""

import hashlib
import json
import math
import os
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from .config import MODEL_ID, MODEL_REVISION, MODEL_SHA256, Settings
from .schema import SystemOneRequest


class InputTooLong(ValueError):
    pass


def stringify(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)


def softmax(values):
    maximum = max(values)
    exps = [math.exp(value - maximum) for value in values]
    total = sum(exps)
    return [value / total for value in exps]


def confidence(probabilities):
    """Normalized negative entropy; this is not TypeSafe's unpublished formula."""
    if len(probabilities) <= 1:
        return 1.0
    entropy = -sum(p * math.log(p) for p in probabilities if p > 0)
    return max(0.0, min(1.0, 1.0 - entropy / math.log(len(probabilities))))


@dataclass
class Prediction:
    # Always entailment, neutral, contradiction, independent of model label order.
    logits: list[tuple[float, float, float]]
    input_tokens: int


class Scorer(Protocol):
    model_id: str
    revision: str

    def predict(self, pairs: list[tuple[str, str]]) -> Prediction: ...


def make_pairs(request):
    state = stringify(request.state)
    pairs, slices = [], []
    for question in request.questions.values():
        instruction = stringify(question.instructions)
        start = len(pairs)
        if question.type == "noul" and question.criteria is None:
            hypotheses = [instruction]
        else:
            if question.type == "choice":
                # Descriptions take precedence; keys only supply labels when null.
                descriptions = [key if value is None else value for key, value in question.criteria.items()]
            elif question.type == "score":
                descriptions = question.criteria
            else:
                descriptions = [question.criteria["true"], question.criteria["false"]]
            hypotheses = [f"{instruction}\n{stringify(description)}" for description in descriptions]
        pairs.extend((state, hypothesis) for hypothesis in hypotheses)
        slices.append((start, len(pairs)))
    return pairs, slices


def evaluate(request: SystemOneRequest, scorer: Scorer):
    started = time.perf_counter()
    pairs, slices = make_pairs(request)
    prediction = scorer.predict(pairs)
    answers = {}
    for (key, question), (start, end) in zip(request.questions.items(), slices):
        logits = prediction.logits[start:end]
        if question.type == "noul":
            if question.criteria is None:
                entailment, neutral, _ = softmax(logits[0])
                # Preserve ignorance: a wholly neutral judgment becomes 0.5.
                probability = entailment + 0.5 * neutral
            else:
                probability = softmax([row[0] for row in logits])[0]
            answers[key] = {"type": "noul", "noul": probability}
            continue
        probabilities = softmax([row[0] for row in logits])
        keys = list(question.criteria) if question.type == "choice" else [str(i) for i in range(len(logits))]
        answer = {
            "type": question.type,
            "probabilities": dict(zip(keys, probabilities)),
            "confidence": confidence(probabilities),
        }
        if question.type == "choice":
            answer["choice"] = keys[max(range(len(probabilities)), key=probabilities.__getitem__)]
        else:
            answer["score"] = sum(i * p for i, p in enumerate(probabilities))
            answer["legend"] = dict(zip(keys, question.criteria))
        answers[key] = answer
    return {
        "model": "openjev-local",
        "answers": answers,
        "usage": {"input_tokens": prediction.input_tokens, "output_tokens": 0},
        "meta": {
            "engine": "local-nli",
            "model_id": scorer.model_id,
            "revision": scorer.revision,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "evaluations": len(pairs),
            "calibrated": False,
            "confidence_method": "1 - normalized entropy",
            "noul_method": "entailment + 0.5 * neutral; explicit criteria use relative entailment logits",
        },
    }


class LocalNLI:
    """Pinned INT8 ONNX model. One candidate per forward preserves isolation.

    Dynamic quantization can otherwise share activation scales across batch
    rows; batch size one also makes option-order comparisons reproducible.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_id = settings.model_id
        self.revision = settings.revision
        self.status = "loading"
        self.error = None
        self.lock = threading.Lock()
        self.tokenizer = self.model = None

    def load(self):
        try:
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
            import onnxruntime as ort
            from huggingface_hub import hf_hub_download
            from transformers import AutoTokenizer

            if self.settings.device != "cpu":
                raise ValueError("The quantized NLI backend currently supports OPENJEV_DEVICE=cpu only")
            kwargs = dict(revision=self.revision, cache_dir=self.settings.cache_dir,
                          local_files_only=self.settings.offline)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=False, **kwargs)
            config_path = hf_hub_download(self.model_id, "config.json", **kwargs)
            with open(config_path) as handle:
                config = json.load(handle)
            labels = {str(label).lower(): int(index) for index, label in config["id2label"].items()}
            if not all(name in labels for name in ("entailment", "neutral", "contradiction")):
                raise ValueError("The model must expose entailment, neutral and contradiction labels")
            self.label_order = [labels[name] for name in ("entailment", "neutral", "contradiction")]
            path = hf_hub_download(self.model_id, "onnx/model_quantized.onnx", **kwargs)
            if self.model_id == MODEL_ID and self.revision == MODEL_REVISION:
                digest = hashlib.sha256()
                with open(path, "rb") as weights:
                    while chunk := weights.read(1024 * 1024):
                        digest.update(chunk)
                if digest.hexdigest() != MODEL_SHA256:
                    raise RuntimeError("Model checksum mismatch. Remove the cached model file and download it again.")
            options = ort.SessionOptions()
            options.intra_op_num_threads = min(4, os.cpu_count() or 1)
            options.inter_op_num_threads = 1
            self.model = ort.InferenceSession(path, sess_options=options, providers=["CPUExecutionProvider"])
            self.input_names = {item.name for item in self.model.get_inputs()}
            self.status = "ready"
        except Exception as exc:
            self.status = "error"
            self.error = f"{type(exc).__name__}: {exc}"
            raise

    def predict(self, pairs):
        import numpy as np

        if self.status != "ready":
            raise RuntimeError("Local model is not ready")
        with self.lock:
            tokenized = self.tokenizer(
                [pair[0] for pair in pairs], [pair[1] for pair in pairs],
                truncation=False, padding=False, verbose=False,
            )
            lengths = [len(row) for row in tokenized["input_ids"]]
            longest = max(lengths)
            if longest > self.settings.max_tokens:
                raise InputTooLong(
                    f"State + question uses {longest} tokens; this model supports "
                    f"{self.settings.max_tokens}. Shorten the state or criteria. Nothing was truncated."
                )
            logits = []
            for i in range(len(pairs)):
                batch = {key: np.asarray([value[i]], dtype=np.int64)
                         for key, value in tokenized.items() if key in self.input_names}
                output = self.model.run(None, batch)[0][0, self.label_order].tolist()
                if any(not math.isfinite(value) for value in output):
                    raise RuntimeError("Model returned non-finite logits")
                logits.append(tuple(output))
            return Prediction(logits=logits, input_tokens=sum(lengths))
