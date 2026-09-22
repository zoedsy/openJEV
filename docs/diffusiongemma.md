# DiffusionGemma GPU recipe

This recipe separates the model server from the local playground. It uses ordinary Docker and SSH, with no cloud-provider account or platform SDK required.

## Prerequisites

- GPU host: Linux **x86_64**, one NVIDIA **H100 80GB** as the reference configuration, Docker Engine with Compose v2 and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
- Driver compatible with the image's CUDA 13 runtime. NVIDIA lists **580 or newer** as the CUDA 13.x compatibility baseline; use a current driver compatible with your host and GPU. See [driver compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).
- Reserve approximately 100 GB of disk for the container image, about 18.9 GB of model files, and compilation/cache growth. This is a planning allowance, not a measured minimum.
- Internet access for the initial image and weight download. Subsequent starts reuse `.data/`.
- Laptop: Python 3.10+ (3.12 recommended) and SSH. The laptop does not need CUDA.

The checked configuration is H100 + Marlin weight-only kernels. NVFP4 describes the checkpoint; it does not mean every operation executes in native FP4. Other GPUs and BF16 deployment are not validated by this recipe.

## Fixed versions

| Component | Pin |
|---|---|
| Model | `nvidia/diffusiongemma-26B-A4B-it-NVFP4` |
| Model revision | `ec4ff3df205028f4e81c954c2227f9312b3ec2ea` |
| Image | `razorback16/openjev@sha256:c131a33e9a341489649c22654fb3c5b6b8c7094ae1ffca8c8e8bee0a37a40da5` |
| Image architecture | `linux/amd64` |
| Observed image runtime | PyTorch `2.13.0+cu130`, CUDA `13.0`, vLLM `0.1.dev21656+gbaa833874` |
| GPU runtime flags | `--linear-backend marlin --moe-backend marlin` |
| Context window | 8192 tokens including template and answer canvas |
| GPU memory utilization | 0.80 |
| Image inputs | Disabled in this recipe |

The specialized vLLM structured-read implementation comes from the pinned upstream image. Do not replace it with an arbitrary `vllm:latest` image and assume the API remains compatible.

## 1. Start on the GPU host

Clone this repository onto the host; private access is required until release. From its root:

```bash
nvidia-smi
docker compose -f deploy/gpu/compose.yaml config
docker compose -f deploy/gpu/compose.yaml up -d
docker compose -f deploy/gpu/compose.yaml logs -f model
```

`deploy/gpu/serve.py` downloads the exact revision, starts the upstream model service, waits for health, and submits Choice, Score, and Noul questions. Look for `OPENJEV_STATUS` with `phase: ready`. Downloads and initial GPU compilation can take several minutes. Model health alone is not the same as completed warm-up.

The image is pulled by digest. `.data/openjev/status.json` records the phase, model revision, and image pin. `.data/openjev/smoke.json` records the startup smoke result. These local files are ignored by Git. The status file is local deployment metadata, not cryptographic attestation of an arbitrary server.

The container's API listens on port 8080, published only at the GPU host's **127.0.0.1:8008**. GPU 0 is selected; edit the Compose device ID if the intended card differs.

```bash
curl --fail http://127.0.0.1:8008/v1/models
docker compose -f deploy/gpu/compose.yaml ps
```

## 2. Connect the laptop

Keep this command running in a terminal:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 8008:127.0.0.1:8008 user@gpu-host
```

In another terminal, from your local clone:

```bash
./run-gpu.sh
```

Visit **http://127.0.0.1:8766/?example=support** and click Run. The UI/API run on your laptop; inference runs on the GPU reached through your tunnel. If both run on the GPU host, omit the model tunnel and access the playground through an additional SSH forward for port 8766.

The adapter checks that the server advertises the expected API. Loopback HTTP alone does not verify the remote weight revision; use this pinned deployment and its status record. No silent fallback to a different model occurs.

## 3. Measure your deployment

```bash
python3 scripts/benchmark.py --example support --repeat 10
python3 scripts/evaluate.py --data eval/smoke.jsonl
```

Client elapsed time includes transport and API handling. `meta.latency_ms` measures the adapter request; the optional stdio transport also supplies `meta.inference_ms`, which includes remote HTTP handling, queueing, and model execution. It is not a GPU-kernel-only timing. See [evaluation recipe](recipe.md) before interpreting the outputs as quality evidence.

## 4. Stop and restart

```bash
# On the GPU host; leaves the downloaded model cache intact.
docker compose -f deploy/gpu/compose.yaml down
# Reuse the cache later.
docker compose -f deploy/gpu/compose.yaml up -d
```

Stopping the local UI or SSH tunnel does not stop the model process. Docker stopping also does not shut down a rented GPU machine; manage the machine separately.

## Optional: persistent authenticated stdio

For environments where you already have authenticated remote command access, the adapter can maintain a persistent Python worker. A normal SSH tunnel is the simpler default.

```bash
export OPENJEV_RELAY_COMMAND='["ssh", "gpu-host"]'
export OPENJEV_RELAY_IDENTITY_FILE=/absolute/path/to/openjev/.data/openjev/status.json
./run-gpu.sh
```

The remote command must execute one shell-command argument, provide stdin/stdout, and have Python 3 available. This worker expects the upstream API on host loopback port **8080**; change the Compose host mapping from `8008:8080` to `8080:8080` when using this route. The identity path points to the host's bind-mounted status file.

Connection establishment happens at startup and is reused. An idle health check runs every 15 seconds; the remote worker exits after 60 seconds without input if its client disappears. Requests are framed with unique IDs; raw terminal mode avoids long-input truncation. A failed request is not automatically replayed. The next request can reconnect. Shutdown closes the worker session. Personal hostnames and launch commands belong in ignored local configuration.

## Troubleshooting

| Symptom | Check |
|---|---|
| Image cannot run on the host | This digest is AMD64; use an x86_64 GPU host. |
| CUDA or driver initialization error | Host driver, NVIDIA Container Toolkit, and Docker GPU access. |
| `loading` for several minutes | Download/compilation logs; wait for `phase: ready` and inspect errors. |
| API connection refused | Model readiness, SSH tunnel, and whether local port 8008 is already in use. |
| 422 on long inputs | The 8192-token window includes instructions and answer slots; shorten or split input. |
| 429 | At most two local requests are accepted simultaneously; retry after completion. |
| High confidence on an incorrect answer | Probabilities are not task-calibrated. Collect labels and evaluate; changing transport does not fix this. |

## Licensing and validation scope

See [THIRD_PARTY.md](../THIRD_PARTY.md) for model terms and attribution. The pinned image/model were exercised on a real H100 with typed requests. The portable Compose packaging is a derived deployment recipe; see [validation](validation.md) for exactly what has and has not been run.
