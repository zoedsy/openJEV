# From a demo to a measured decision tool

This recipe provides typed inference, a bilingual ticket-triage workspace, latency measurement, evaluation and offline temperature fitting. It does not reproduce Jev's training method or establish that its current probabilities are reliable for your task.

## What is implemented

| Goal | Current implementation | Remaining evidence |
|---|---|---|
| Return Choice / Score / Noul | Validated typed responses | Not complete TypeSafe SDK compatibility |
| Read scores without generating prose | MiniLM candidate scoring or DiffusionGemma label probabilities | A valid schema does not establish a correct judgment |
| Fast decisions | Small CPU route, GPU typed reads, connection reuse | Measure input lengths, transport and concurrency on your own deployment |
| Independent questions | MiniLM evaluates candidate pairs independently | DiffusionGemma uses a shared canvas and has no isolation guarantee here |
| Useful probabilities | Raw probabilities plus optional offline temperature fitting | Representative calibration and untouched test sets are required |
| Match Jev overall | No paired benchmark | Same inputs, metrics and explicit latency/cost accounting |

TypeSafe describes calibration-oriented training and independent, parallel questions. Those are comparison targets, not results established by a few examples: [System One](https://docs.typesafe.ai/concepts/system-one), [primitives](https://docs.typesafe.ai/primitives), [training objective](https://docs.typesafe.ai/introduction/machine-learning-primer).

## 1. Define a task and its labels

Start with a task such as support-ticket triage. Write down the service scope, category definitions and urgency rubric before inspecting model outputs. Missing messages remain unscored; unclear categories need an explicit fallback. Reading “urgent” in a message is different from independently proving urgency.

Use fictional examples to test the workflow. For a quality assessment, collect permitted, de-identified messages and human labels; include ambiguous, irrelevant, negated and incomplete inputs. Keep each conversation and its derived versions in one group, then split training/development, calibration and test data by group.

The bundled fixtures are synthetic: two smoke requests, six calibration cases and seven test cases. They exercise code paths and cannot establish real support accuracy.

## 2. Measure the unchanged baseline

```bash
python3 scripts/evaluate.py --data eval/smoke.jsonl
python3 scripts/evaluate.py --data /path/to/your-test.jsonl --out artifacts/your-evaluation.json
python3 scripts/benchmark.py --example support --repeat 30
```

Reports retain request failures, invalid answers and unlabeled questions. Inspect accuracy, NLL, Brier score, ECE and Score error, including language/source slices. Small ECE on a small sample is not proof of calibration. Latency reports separate one warm-up from sequential client p50/p95; repeated inputs may benefit from caches.

## 3. Test structural behavior

For the same message, compare its full distributions when:

1. A question is asked alone versus alongside unrelated questions.
2. Candidate order changes, mapped back to the same labels.
3. The number of questions increases from one to several.
4. Inputs include negation, missing details and out-of-scope requests.

DiffusionGemma's shared canvas provides no guarantee for the first two checks. MiniLM's isolated candidate pairs make the dependency structure simpler, but its instruction understanding and context window are more limited.

## 4. Improve and re-evaluate

1. Fix unclear labels and prompts on development data.
2. If errors persist, consider a supervised classifier or a compatible trainable base model using the training partition. No such new model has been trained here.
3. Freeze the selected model and rubric, then use the [offline calibration guide](evaluation.md). Fit on calibration data only; compare on untouched test data. Temperatures can improve or worsen held-out metrics and usually preserve categorical ranking.
4. Check new sources, languages and time periods for drift. Do not enable a transform just because fitting loss decreased.

[Kev](https://github.com/jaredpalmer/kev) and [NanoJev](https://github.com/TianyuCodings/NanoJev) provide public training implementations to inspect. The NVFP4 checkpoint served here is an inference artifact; this recipe does not provide direct training of those quantized weights or a reproduction of TypeSafe's RLCD.

Report quality, calibration, latency, cost and question isolation separately. See [use cases](use-cases.md) for other tasks and the [validation record](validation.md) for the scope of checks performed here.
