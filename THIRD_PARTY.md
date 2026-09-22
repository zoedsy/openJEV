# Attribution and model terms

This repository's original playground, adapter, tests, and deployment recipe use the MIT license. That license does not replace the terms of dependencies or downloaded models.

| Component | Source and terms | Used here |
|---|---|---|
| MiniLM NLI | [Original model](https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli), MIT; [ONNX conversion](https://huggingface.co/onnx-community/multilingual-MiniLMv2-L6-mnli-xnli-ONNX) | Downloaded at a pinned revision; not redistributed |
| DiffusionGemma checkpoint | [NVIDIA model card](https://huggingface.co/nvidia/diffusiongemma-26B-A4B-it-NVFP4) labels the checkpoint Apache-2.0 and also lists Gemma Terms of Use and Gemma Prohibited Use Policy as governing terms | Downloaded by the GPU recipe; not redistributed or relicensed |
| DiffusionGemma decision server | [razorback16/openjev](https://github.com/razorback16/openjev), Apache-2.0 | Separately distributed, pinned Docker image provides structured reads and its vLLM build |
| Kev | [jaredpalmer/kev](https://github.com/jaredpalmer/kev), Apache-2.0 code; model terms in its model cards | Optional HTTP integration; not bundled |
| API inspiration | [TypeSafe public documentation](https://docs.typesafe.ai/introduction) | Independently implemented subset; no Jev weights, branding assets, or private training code |

Consult each source's actual license and model terms before redistributing its artifacts. The project name is also used by other independent repositories; this repository is not their official branch. Dependency installation and model downloads use upstream distributions rather than copied weights in Git.

Contribution-specific credits are collected in [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).
