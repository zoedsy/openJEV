# openJEV and razorback16/openjev

Our GPU route depends on [razorback16/openjev](https://github.com/razorback16/openjev). Its server supplies the DiffusionGemma structured-read implementation used by our adapter. This repository does not contain a newly trained model or an independently developed replacement for that serving implementation.

| Area | razorback16/openjev | This repository: openJEV |
|---|---|---|
| Main focus | DiffusionGemma decision-serving API | A decision playground and bilingual batch ticket workspace, with backend adapters and deployment/evaluation recipes |
| DiffusionGemma inference | Implements typed reads and label-probability extraction | Connects to a pinned upstream image and validates the responses |
| Model routes | Documents vLLM on NVIDIA GPUs and MLX on Apple silicon | CPU MiniLM by default; DiffusionGemma through an external GPU service; optional Kev adapter |
| Interaction | API and client examples | Browser editor, probability charts, request export, local history, and a CSV/JSON ticket workspace with pause/resume and complete exports |
| API scope | Documents typed decisions, images, text generation, and additional sampling/thinking controls | Text-only Choice / Score / Noul plus bounded, non-streaming chat generation and explicit capability discovery; no images, streaming or advanced sampling controls |
| Deployment | Provides its own Docker and serving instructions | Adds a pinned H100 recipe, laptop-to-GPU connection instructions, local launchers, and optional persistent stdio transport |
| Evaluation | Has its own upstream tests and reported results | Adds adapter/transport and browser tests, latency measurement, per-slice JSONL evaluation, and offline temperature fitting with split/provenance checks; synthetic data is not a quality benchmark |
| Model quality | Determined by the upstream model and inference method | No new training or demonstrated quality advantage over the upstream server |

The upstream column summarizes its [README](https://github.com/razorback16/openjev/blob/main/README.md), checked on 2026-09-22. Features it documents are not all validated or exposed by our pinned deployment. Our current API limits and validation evidence are recorded in [the API guide](api.md) and [validation record](validation.md).

For the GPU route, our current contribution is primarily the surrounding application, integration, reproducibility, and measurement. The CPU NLI route is a separate lightweight implementation with different capabilities and limitations. Neither route establishes parity with Jev's accuracy, probability calibration, or multi-question independence.

The projects are independently maintained and use similar names. We credit the upstream serving authors in [ACKNOWLEDGEMENTS.md](../ACKNOWLEDGEMENTS.md); their code and model terms are not replaced by this repository's MIT license.
