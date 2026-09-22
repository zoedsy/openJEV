# Evaluation and offline probability calibration

openJEV includes a reproducible evaluation pipeline, not a claim that the current model beats Jev or another implementation. The bundled examples are **hand-authored synthetic fixtures**. They test data handling, Chinese/English prompts, negation, missing information, and rubric boundaries; they do not establish real support-ticket routing accuracy or calibration.

The current NVFP4 DiffusionGemma deployment is used for inference. This repository does not contain newly trained DiffusionGemma weights, Jev's training data, or a reproduction of Jev's RLCD training method. Calibration here is an optional offline postprocessing experiment. It is never activated on the running API or playground.

## Collect labels before optimizing scores

For a real support-ticket routing application:

1. Fix the routing categories and urgency rubric before looking at model answers. Define which explicit requests count as refunds, which messages concern delivery or product help, and how a stated deadline maps to each urgency level. Include an `insufficient_information` or `other` Choice class when the categories do not cover every ticket.
2. Collect tickets with permission to use them for evaluation. Record a pseudonymous conversation ID, language, collection period, channel, and inclusion rules. Remove names, contact details, addresses, order identifiers, credentials and unrelated private text. Include unclear requests, neighboring categories, explicit negation, hypothetical future requests, and messages without deadlines. Permission to inspect a support conversation does not automatically include permission to publish it.
3. Have two annotators independently label each ticket using the same visible messages as the model. Preserve their original labels, resolve disagreements, and record the reason. A label such as `refund_requested` describes the current request; it does not determine refund eligibility or authorize a payment. An urgency label follows the stated deadline rubric, not the customer's emotional tone.
4. Use a `group_id` for a conversation and all its turns, translations, summaries, or derived examples. Keep related conversations from the same customer or incident together when they could reveal the same outcome. Split by group before prompt tuning or fitting. Keep separate **training/development**, **calibration**, and untouched **test** partitions. A possible starting allocation is 60/20/20, adjusted to retain enough examples of every important class; the ratio alone does not make a dataset adequate. For deployment drift, a later-time test set can be more revealing than a random split.
5. Freeze the rubric, prompts, candidate order, model revision, quantization and serving configuration. Fit temperatures only on the calibration split. Use the test set to report results, never to choose a temperature, threshold, prompt, or checkpoint. If decisions change after seeing it, use a new untouched test set for the next claim.

A binary Noul question cannot represent “unknown” as a separate outcome. Ask an observable statement such as “does the customer explicitly request a refund now?” if absence should mean false. A possible future refund or an explicit refusal is not a current request. For a factual question where the ticket provides no answer, either use a Choice with an insufficient-information class or leave the expected label `null`. Missing evidence is not automatically a false factual claim.

## Dataset and response format

Each JSONL row contains `id`, `request`, and `expected`. Every question needs a corresponding expected label. Optional `slices` produce subgroup reports. A calibration row must declare `split: "calibration"`; evaluation with fitted parameters requires `split: "test"`.

```json
{"id":"ticket-001","group_id":"conversation-001","split":"test","slices":["en","negation"],"request":{"state":"I do not want a refund. Please help me turn on the speaker.","questions":{"refund_requested":{"type":"noul","instructions":"The customer explicitly requests a refund now."}}},"expected":{"refund_requested":false}}
```

Choice targets are candidate names; Noul targets are `true`/`false` (or 1/0); Score targets use **zero-based rubric levels**. An integer Score label supports categorical metrics and fitting. A fractional average of annotators' levels supports MAE only; it is not silently rounded into a categorical label. `null` marks an explicitly unlabeled question and is retained but excluded from metrics. An `insufficient_information` candidate is an ordinary labeled class and is evaluated normally.

Response artifacts preserve every sample's request, labels, original response, and errors. They also include dataset fingerprints and slices. Old artifacts containing only `results: [{"id": ..., "response": ...}]` remain readable when paired with the exact dataset; because they lack recorded request provenance, check that pairing yourself. New artifacts verify recorded requests and labels against the supplied data.

Artifacts contain the input text and labels. Keep private customer data in ignored `artifacts/` or another private location, not in a public repository.

## Run a pipeline smoke check

The bundled splits contain six calibration tickets and seven test tickets, all fictional online-store interactions. Their questions cover routing category, an explicit current refund request, and urgency from an explicit support deadline. Chinese/English, negation, hypothetical future plans, missing information and an intentionally unannotated `null` label exercise the pipeline.

Start an existing backend using the repository's deployment instructions. The following commands make **sequential** API calls to that service; they do not create GPUs or download weights by themselves. Both backends can be evaluated, but their calibration parameters are separate.

```bash
python scripts/evaluate.py --data eval/smoke.jsonl --out artifacts/smoke-evaluation.json

python scripts/evaluate.py --data eval/synthetic-calibration.jsonl --out artifacts/synthetic-calibration-raw.json
python scripts/calibrate.py --data eval/synthetic-calibration.jsonl --responses artifacts/synthetic-calibration-raw.json --min-samples 2 --out artifacts/synthetic-temperature.json

python scripts/evaluate.py --data eval/synthetic-test.jsonl --out artifacts/synthetic-test-raw.json
python scripts/evaluate.py --data eval/synthetic-test.jsonl --responses artifacts/synthetic-test-raw.json --calibration artifacts/synthetic-temperature.json --out artifacts/synthetic-comparison.json
```

`--responses` is entirely offline: it reuses saved responses without a model call. `--min-samples 2` is intentionally only for this small **pipeline demonstration**. The default is 20 labeled questions per type; even 20 is a minimum fitting guard, not evidence of statistical adequacy. Collect enough representative independent conversations, including mistakes and rare categories, before making a calibration claim.

For real data, use the same commands with your calibration/test files and omit the demo minimum override. `OPENJEV_API_KEY` is used for API authentication when set. `--url` selects an existing API; `--timeout` changes its per-request timeout.

The command writes its report after each request. Network failures and invalid answers stay in the report instead of disappearing from the denominator. Invalid questions are reported with sample/question IDs while other valid questions can still be scored. A report with request, answer, or calibration errors exits with code 1; a malformed dataset or incompatible split exits with code 2. Interrupted runs retain unattempted/interrupted statuses. Exact NaN/Infinity values from malformed outputs are represented by an `invalid_nonfinite_number` marker so the report remains valid JSON.

Calibration fitting refuses a response file with failed requests. Resolve those failures or make an explicit, documented dataset revision; silently dropping difficult examples would bias the experiment. Re-run failed requests against the same frozen model and configuration before fitting.

## Read the metrics

| Type | Metrics | Interpretation |
| --- | --- | --- |
| Choice | Accuracy, categorical NLL, multiclass Brier sum, top-label ECE in 10 equal-width bins | NLL and Brier evaluate the whole probability assignment. ECE compares predicted top-label probability with observed correctness within bins. |
| Noul | Accuracy at 0.5, binary NLL, binary Brier, positive-class ECE | The probability of true is evaluated against a binary observed label. An application-specific threshold must be chosen outside the test set. |
| Score | MAE in zero-based rubric levels; categorical NLL/Brier/top-label ECE and argmax accuracy when raw probabilities and integer labels exist | A prediction of 1.4 against target 2 has absolute error 0.6 **rubric levels**. Argmax accuracy evaluates the most probable level, separately from expected-score MAE. |

NLL uses natural logarithms and a documented probability floor of `1e-12` for finite metrics. Brier sums are not normalized by class count, so compare the same task/candidate set. The same caution applies to NLL and mixed Score rubrics. Historical Score responses without a probability distribution still produce MAE and explicitly report missing probability coverage.

Reports include `by_type`, per-slice metrics, `n`/`nll_n`, unlabeled counts, and failures. The legacy top-level `choice`, `noul`, and `score` fields remain available. Slices can overlap; adding their counts double-counts samples. Questions or turns from one conversation are correlated, so more question rows are not equivalent to more independent conversations. Do not claim precise calibration from a tiny ECE value on a small set. This tool does not yet calculate statistical confidence intervals; for publication, add a group-level bootstrap or other justified uncertainty analysis and retain all failed cases.

The API's `confidence` field summarizes distribution concentration. This evaluator **does not use it as the probability that an answer is correct**.

## What the calibration changes

For a categorical probability vector `p`, a fitted positive temperature `T` computes `softmax(log(max(p, 1e-12)) / T)`. Noul is treated as the two-class vector `[1-p, p]`; Choice and Score use their full candidate distributions. A standard-library bounded optimizer chooses one temperature per question type by minimizing calibration-split NLL in the range `[0.05, 20]`. Parameters at a bound are flagged in fitting diagnostics.

Temperature scaling follows the postprocessing approach described by [Guo et al., *On Calibration of Modern Neural Networks* (ICML 2017)](https://proceedings.mlr.press/v70/guo17a.html). Its usefulness on another model or task must still be measured.

The parameter file includes format/method versions, model ID/revision and available serving identity, temperature bounds, the calibration data source, sample/group IDs, request/data/raw-prediction fingerprints, skipped labels, and fitting diagnostics. A content fingerprint detects accidental file changes; it is not a security signature. Evaluation rejects overlapping calibration/test IDs, exact request contents, or supplied group IDs, as well as mismatched model/serving identities. It cannot automatically detect every paraphrase or data leak: keep related examples in the same group. Changing the model revision, quantization, inference implementation, task domain, prompts or rubric calls for revalidation and usually a fresh fit.

Types without enough labeled data are explicitly marked unfitted. Their answers stay unchanged in a comparison and are listed under `uncovered_questions`; partial coverage never silently marks the full response calibrated. Original raw responses are always preserved. A model/revision mismatch becomes a recorded calibration error with a failing exit code.

`summary.calibration.before` and `.after` use exactly the same successful paired test requests. Compare held-out NLL, Brier, ECE and task-specific metrics, including every important slice; gains on the fitting split are only optimizer diagnostics. Temperature scaling preserves categorical ranking (apart from ties/numerical clipping), so it generally **does not improve Choice accuracy or Noul accuracy at 0.5**. It changes Score expectations, which can help or harm MAE. It can also worsen held-out probability metrics. Do not enable a fitted transform for users merely because its training NLL went down.

## A route toward better judgments

1. Establish an untuned real-data reference evaluation and retain a case review of wrong, unknown and failed outputs.
2. Improve the label definitions, candidate coverage and prompts on development data; test isolation effects such as whether adding another question changes the first answer.
3. If recurring errors remain, train a small supervised classifier or investigate supervised fine-tuning of a compatible trainable base model on the training split, with validation-based checkpoint selection. Preserve source licenses and document model, data and optimization settings. The served NVFP4 inference weights are not presented here as an already fine-tuned training checkpoint.
4. After selecting and freezing that model, refit calibration using only the calibration split, then evaluate once on an untouched test set. Report latency, failures, quality and probability metrics separately.
5. Compare with an upstream implementation or Jev only when both can actually be run on the same permitted held-out inputs and rubric. Publish the configurations, paired results and uncertainty; no such head-to-head result is supplied by these fixtures.

This repository currently implements evaluation and offline temperature fitting. It has not trained a new DiffusionGemma model or reproduced Jev's proprietary training procedure.
