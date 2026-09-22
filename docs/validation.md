# Validation record

Reference check: 2026-09-22. These checks concern this implementation; they do not establish equivalence to Jev or an improvement in the underlying model.

## Executed checks

- **144 CPU-only tests passed** after replacing the bundled evaluation data: API and probability contracts, bounded inputs, authentication, model identity, persistent transport, concurrent response matching, failure handling, strict text generation, capability discovery and calibration provenance.
- **2 real MiniLM checks passed** using the pinned ONNX weights on macOS / CPU: English and Chinese decisions, support versus contradiction, independent questions and option-order consistency.
- **Real H100 inference** uses the NVIDIA DiffusionGemma 26B-A4B NVFP4 checkpoint at revision `ec4ff3df205028f4e81c954c2227f9312b3ec2ea`, with the pinned image and settings in the [GPU recipe](diffusiongemma.md).
- A short real text-generation request returned `OK`, `finish_reason=stop`, and six reported completion tokens in **3.461 seconds** end to end. This tests the endpoint, not general generation quality or a latency distribution.
- The current **fictional customer-service evaluation pipeline** ran six calibration cases and seven separate test cases through the GPU. All seven test responses paired successfully for offline comparison, with no request or calibration errors. One Score label was intentionally absent. The fitted temperatures hit their lower bound and were flagged; these tiny, easy fixtures cannot justify deployment calibration. Online responses retain raw probabilities.
- **29 JavaScript checks passed**: nine ticket parsing/export checks, fourteen ticket browser checks and six playground browser checks with controlled HTTP fixtures. They cover English defaults, Chinese switching, frozen batch rules, auth, queue recovery, safe exports and selective old-demo-history clearing.
- **Real bilingual browser check**: the single-request support example displayed three actual GPU decisions in **636.6 ms** at the adapter. Four fictional batch tickets completed in **3.742 seconds**; the fifth, missing a message, was not sent. Each completed ticket had one attempt and none failed. Adapter times ranged from **219.4 to 2233.6 ms**, with remote model-service times **40.3–60.9 ms**. These are workflow observations, not general performance guarantees.
- English and Chinese interfaces were checked in a real browser at desktop and 390px mobile widths, with no horizontal overflow or JavaScript errors. JSON export retained the original batch rules after switching the interface language.
- A wheel was rebuilt from a clean generated-build directory. It contains the current ticket assets, chat adapter and calibration module; retired demo assets and personal deployment files are absent.
- The portable Compose YAML was parsed and its image digest, AMD64 architecture, loopback port mapping and bootstrap mount were checked.

## Timing interpretation

`meta.inference_ms` covers the remote model-service HTTP request, including possible queueing; it is not GPU-kernel time. `meta.latency_ms` includes the transport used by the adapter. The benchmark script separately measures the complete local HTTP request and records one warm-up outside the measured sample.

Transport jitter can dominate model-service time. The main playground stops waiting after 120 seconds and explicitly says the server may still be processing; it does not automatically replay the request. The batch workspace pauses after uncertain failures. A few successful requests do not establish a stable p95, throughput or fresh-input performance.

Run `python3 scripts/benchmark.py --example support --repeat 30` on your own deployment. Repeated inputs can benefit from caches. Preserve every observation, including failures, and report input length, concurrency, warm-up and sample count. Local evidence remains in ignored `artifacts/`.

## Not established

- A fresh Docker Compose installation on a second GPU host. The same image, model, H100 parameters and bootstrap logic ran on a real GPU; the Compose wrapper was checked statically on this laptop.
- Alternative GPUs, BF16 serving, production concurrency, failover or cost per decision.
- Representative real-data task accuracy, deployment calibration or a paired Jev benchmark.
- Question isolation for DiffusionGemma; questions share a canvas.
- Kev model quality; its HTTP adapter is the tested component here.
- New model training, decision-head fine-tuning or an RLCD reproduction.
