# Contributing

Start with the CPU quickstart in the README; it requires no GPU or paid API. Changes to HTTP, probability handling, or transports should include relevant contract tests. Run `python -m pytest -q -m 'not model'` before submitting changes.

For GPU changes, record the exact image digest, checkpoint revision, hardware, inputs, warm-up, and measured request count. Distinguish an adapter test from actual model inference. Do not claim calibration or parity with Jev based on a UI demonstration.

Keep private hostnames, account names, job identifiers, API keys, model caches, and request logs out of commits. `.private/`, `.data/`, `.models/`, and `artifacts/` are intentionally ignored. Use generic placeholders in deployment instructions. Use invented, task-neutral demonstrations rather than unpublished work, real customer data or private workflows. Review screenshots, evaluation fixtures, commit messages and test logs as part of the same check.

Changes that alter probabilities should document their formula and test source. Keep evaluation data separate from training or calibration data. Cite upstream code and model sources; the MIT license does not relicense external weights.
