# Support ticket workspace

Open **[the local support workspace](http://127.0.0.1:8766/tickets)** after starting openJEV. The static entry point is `/static/tickets.html`.

1. Describe the services your team supports.
2. Paste or upload CSV or JSON, then select **Preview & validate**. Every ticket needs a title and message; channel and URL are optional.
3. Inspect the original messages and shared rubric, then select **Start triage**.
4. Sort by scope signal or urgency, inspect each result, and export CSV or JSON before closing the page.

**Try fictional examples** loads five ordinary online-shop messages with no real customers or transactions. Four contain messages; the fifth demonstrates missing input. They are workflow examples, not a benchmark. No model outputs are prefilled.

![Support workspace](tickets-workspace.png)

## English and Chinese

English is the default interface. The language selector also offers Simplified Chinese. Only this preference is saved in browser storage, under `openjev.locale` with the value `en` or `zh`. Input, API keys and batch results remain in page memory.

Switching language updates the interface, validation messages, fictional examples and the rubric for a new batch. Once a batch starts, its service scope, ticket contents, rubric and language are frozen. Switching the interface does not change those requests. Details and JSON exports retain the actual input language and rules. Old demo history is cleared on first opening.

## Input format

CSV requires `title,message` and optionally `channel,url`. Chinese aliases are `标题,内容,渠道,链接`. Standard quoted fields preserve commas, embedded quotes and line breaks. JSON accepts an array of ticket objects or an object with a `tickets` array:

```json
[
  {
    "title": "Delivery update requested this week (fictional demo)",
    "message": "Please check the expected delivery date this week. This is a fictional example.",
    "channel": "Web form",
    "url": "https://example.org/tickets/demo"
  }
]
```

Each batch supports up to 100 rows and 2 MiB of input. A message is limited to 16,000 characters; the configured model's token window may impose a smaller limit. Oversized requests fail explicitly rather than silently truncating content. MiniLM has a 512-token window, so longer messages and the shared rubric may require a backend with more context.

Missing messages remain **Unassessed**, without a scope or priority result. Invalid titles, field types and sizes are kept for correction. Duplicate title/message pairs remain separate records with a warning. Unsafe or malformed links are not clickable.

## Decisions and their limits

Every valid ticket uses one `POST /v1/systemone` request. Its state contains `service_scope` and a `ticket` with title, message and channel. It asks three questions:

| Key | Type | Meaning |
| --- | --- | --- |
| `in_scope` | Noul | An uncalibrated 0–1 signal that the request falls within the described service scope. |
| `category` | Choice | Stable keys: `account`, `payment`, `delivery`, `issue`, `inquiry`, or `other`. The interface displays localized category names. |
| `priority` | Score | A probability-weighted 0–3 urgency score based on explicit timing or stated impact. |

The four urgency levels are:

0. No explicit deadline or widespread blockage stated.
1. Explicitly needs handling this week, without a same-day deadline.
2. Explicitly needs handling today, without a one-hour deadline or widespread blockage.
3. Explicitly needs handling within one hour, or describes a widespread service blockage.

The full rubric is visible before starting and alongside every record. Priority can be fractional. No deadline is inferred merely from an emotional tone. These signals assist human triage; the workspace does not send customer messages, promise service levels or resolve tickets. Confidence describes the concentration of a distribution, **not accuracy**. Questions within one request may influence one another on a shared-canvas backend.

## Running and recovering

Requests are sequential within each page. **Pause next items** waits for the current request to finish and prevents later tickets from starting. **Resume pending** continues pending records. **Retry failures** requeues failed items and resumes the remaining queue without resending completed records.

HTTP 429 gets at most two automatic retries per invocation, with a bounded delay based on `Retry-After`. A network failure, timeout, authentication failure, malformed response or service outage pauses later work and marks the current ticket as failed. A timed-out request may already have reached the server, so it is not automatically replayed. Check the service before retrying manually. HTTP 413/422 affects the current item while allowing the queue to continue.

The actual processing location comes from `/api/status`. API keys stay in page memory and never enter an export. This browser workspace is not a multi-user job server: tabs have independent queues, and reloading loses the in-memory batch. Export first.

CSV and JSON exports include **every record**, regardless of table filters. CSV fields that could execute as spreadsheet formulas receive a leading apostrophe. JSON keeps original messages, the exact request, the raw response and the frozen rubric. CSV includes run and model identifiers for convenient sorting; use JSON for complete reproducibility.

## Tests

The dependency-free logic checks use:

```sh
node --test tests/tickets.test.cjs
```

Optional browser checks use a controlled HTTP test service and synthetic outputs:

```sh
node --test tests/tickets-browser.test.cjs
```

Install Playwright and Chromium first. `BROWSER_CHANNEL=msedge` selects an installed Edge; `PLAYWRIGHT_MODULE` can point to an existing Playwright installation. The tests cover import validation, missing messages, queue controls, retry and failure behavior, authentication, safe rendering and exports, English defaults, Chinese switching and frozen batch rules. Synthetic test responses do not establish model accuracy.

## Real-model workflow check

On 2026-09-22, the four fictional demo messages completed once each against the configured DiffusionGemma GPU service; the missing-message row stayed unassessed. The batch took 3.742 seconds in that run. Both language settings and a 390px viewport were checked; switching the interface preserved the exported run. This confirms a working path, not stable latency, real-world accuracy or calibrated probabilities. See the [validation record](validation.md).
