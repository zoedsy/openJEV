# Acknowledgements

openJEV builds on open models, open-source software, and public documentation. We thank the following authors and communities for the work that makes this project possible.

- **Google DeepMind and the Gemma team** for [DiffusionGemma](https://huggingface.co/google/diffusiongemma-26B-A4B-it), the model underlying our GPU inference route.
- **NVIDIA** for the [DiffusionGemma NVFP4 checkpoint](https://huggingface.co/nvidia/diffusiongemma-26B-A4B-it-NVFP4) used by the pinned deployment recipe, and the quantization tooling behind it.
- **The authors and contributors of [razorback16/openjev](https://github.com/razorback16/openjev)** for the DiffusionGemma structured-read decision server and Docker image that our GPU adapter connects to. The upstream server provides the model-side implementation; this repository adds its own playground, adapter, deployment recipe, and evaluation tools.
- **The [vLLM community](https://github.com/vllm-project/vllm)** for the inference runtime used by the pinned upstream image and its structured-read integration.
- **TypeSafe AI** for Jev's [public documentation](https://docs.typesafe.ai/introduction), especially the [Choice, Score, and Noul primitives](https://docs.typesafe.ai/primitives), state/question interface, and [discussion of confidence](https://docs.typesafe.ai/confidence). These documents inspired this project's typed-decision interface and examples.
- **Moritz Laurer and the ONNX Community** for the [multilingual MiniLM NLI model](https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli) and its [ONNX conversion](https://huggingface.co/onnx-community/multilingual-MiniLMv2-L6-mnli-xnli-ONNX), which power the CPU quickstart.
- **Jared Palmer and the [Kev contributors](https://github.com/jaredpalmer/kev)** for an open decision-model implementation and API that our optional Kev adapter can use. Additional investigated projects are credited in the [alternatives survey](docs/alternatives.md).

openJEV is an independent project. These acknowledgements do not imply affiliation, sponsorship, or endorsement. We do not include Jev's weights or private training method, and we do not claim to reproduce its model quality, calibration, or performance. We do not claim authorship of the upstream models or serving implementation.

Licenses and model terms remain with their respective owners. See [THIRD_PARTY.md](THIRD_PARTY.md) for source and licensing information, separately from the [MIT license](LICENSE) covering this repository's original code.
