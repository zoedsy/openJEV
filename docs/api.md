# API: decisions, capabilities, and bounded text generation

The local service defaults to `http://127.0.0.1:8766`. Configure `OPENJEV_API_KEY` to require `Authorization: Bearer ...` on `/v1/*` routes. Capability and status responses are public metadata and never include the key or remote launch command. The server accepts at most 256 KiB per request, including requests without `Content-Length`.

## Discover what this deployment can do

```bash
curl --fail http://127.0.0.1:8766/api/capabilities
```

The response separates `supported` (implemented by this adapter) from `available` (ready now), with an `unavailable_reason`. It describes typed decisions, generation, image support, and limits. DiffusionGemma generation availability requires a ready backend and an upstream `/v1/models` entry named `diffusiongemma-26b`. This is a readiness check, not a claim about generation quality or an end-to-end GPU benchmark.

| Capability | CPU MiniLM | Kev adapter | DiffusionGemma adapter |
|---|---|---|---|
| Choice / Score / Noul | Yes | Yes | Yes |
| Text generation | No, returns 501 | No, returns 501 | Text-only subset below |
| Images | No | No | Disabled in this recipe |
| Streaming generation | No | No | No; `stream=true` returns 422 |
| Probability calibration | Not established | Not established here | Not established |
| Questions isolated from one another | Independent candidate pairs | Not verified here | No guarantee: shared answer canvas |

Capabilities describe this repository's adapters. They do not enumerate every feature the upstream projects might offer. A failed connection never switches to a different model.

## Typed decisions

`POST /v1/systemone` retains the existing `state`, `questions`, and optional `model` contract. It accepts `openjev-local`, `openjev-latest`, and `jev-latest` aliases.

```json
{
  "state": "The parcel arrived damaged. Please send a replacement.",
  "questions": {
    "replacement_requested": {"type": "noul", "instructions": "The customer explicitly requests a replacement."}
  }
}
```

The schema allows 1–32 questions, 2–10 score levels, and up to 256 candidate evaluations as counted by the request validator. A DiffusionGemma Choice has at most 128 options; the general schema allows 255. The serialized state is limited to 60,000 characters. Token limits are checked by the model service; text is not silently truncated. MiniLM's context applies to each state/question pair. DiffusionGemma's configured 8192-token window includes the prompt template and output canvas.

A probability is model output, not a measured accuracy guarantee. A generated explanation also does not establish why a separate typed decision was made.

## Text generation

`POST /v1/chat/completions` provides a deliberately limited OpenAI-style request and response format. It is not a claim of complete OpenAI API or SDK compatibility. Use `model: "diffusiongemma-26b"`; decision aliases do not select the generation endpoint.

```bash
python3 examples/chat_client.py --prompt 'Summarize: The parcel arrived damaged and the customer requests a replacement.' --max-tokens 64
```

Equivalent request:

```json
{
  "model": "diffusiongemma-26b",
  "messages": [
    {"role": "system", "content": "Answer briefly using only the supplied text."},
    {"role": "user", "content": "Summarize this fictional support request: The parcel arrived damaged and the customer requests a replacement."}
  ],
  "max_tokens": 64,
  "stream": false
}
```

Only these fields are accepted:

| Field | Contract |
|---|---|
| `model` | `diffusiongemma-26b`; this value is also the default |
| `messages` | 1–32 messages; each contains only `role` and string `content` |
| Message roles | `system`, `user`, `assistant`; optional system message only first, last message must be user |
| Message content | Nonblank text; at most 16,000 characters each, 32,000 characters total |
| `max_tokens` | Integer 1–512, default 128; strings, booleans, zero, and larger values are rejected |
| `stream` | Must be `false` when supplied; defaults to `false` |

Images/content-part arrays, tools, JSON schema outputs, `temperature`, `seed`, `top_p`, penalties, `max_completion_tokens`, thinking controls, and other unlisted parameters return **422**. They are not accepted and then silently ignored. These bounds are checked before contacting the model. Character limits do not predict token counts: the upstream tokenizer can still reject a request whose prompt plus output exceeds the context window. Generation uses the pinned service's default sampling behavior with thinking disabled; sampling controls are not exposed here.

Successful responses preserve the upstream `chat.completion` object, single assistant text choice, `finish_reason`, and token `usage`. The adapter validates these fields and rejects malformed output or usage exceeding the requested output budget. `finish_reason: "length"` means generation reached the requested limit; the client should not treat that as a complete answer.

Generation requires more model work than a typed read. Both routes share two local request slots, and the GPU recipe limits active upstream generations to one. There is no automatic retry after an uncertain remote connection failure; repeating a request is a client decision.

## Errors and validation scope

| Status | Meaning |
|---|---|
| 401 | Missing or invalid API key |
| 413 | Body exceeds 256 KiB |
| 422 | Invalid local schema or unsupported parameter; no model call |
| 429 | Both local request slots occupied (`Retry-After: 1`) |
| 501 | Configured adapter lacks generation, or the ready service does not advertise the generation model |
| 503 | Local backend still loading or unavailable (`Retry-After: 3`) |
| 502 | Transport failed, redirect refused, or upstream returned an invalid completion |
| Other upstream errors | Generation preserves the real upstream HTTP status and JSON error body, including 400, 422, 429, 503, or 529 |

Local validation uses FastAPI's `detail` format; upstream errors can use an `error` object. Check the HTTP status before reading a completion. Direct loopback HTTP also preserves a numeric upstream `Retry-After`; the optional stdio relay currently preserves status and body, not upstream response headers.

The adapter is checked with real loopback HTTP servers and mock remote transports: authentication, body/input limits, explicit parameter rejection, error propagation, result validation, and shared concurrency. These contract tests do not measure GPU generation quality. A separate real H100 smoke request also returned a valid completion; its narrow scope and timing are in the validation record. See [deployment recipe](diffusiongemma.md) and [validation record](validation.md) for deployment evidence.

Generation delegates to [razorback16/openjev's pinned implementation](https://github.com/razorback16/openjev/blob/e04794ab36e4f7e6040c2547baecdb2737ce2e79/openjev/chat.py). This wrapper restricts the public contract because the upstream implementation intentionally normalizes or drops some parameters. Model/server attribution and terms remain in [THIRD_PARTY.md](../THIRD_PARTY.md).
