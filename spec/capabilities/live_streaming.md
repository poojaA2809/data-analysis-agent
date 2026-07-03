# Capability: Live Streaming Step Updates

## What It Does
Streams the agent's progress ("Planning…", "Generating code…", "Running code…", "Checking result…", "Charting…", "Writing answer…") and the final answer to the browser as they happen, over a single-request SSE POST. Delivered in Phase 3.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | user | yes |
| dataset_ids | list[str] | session | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| step events | SSE `step` `{label}` | live step indicator |
| token events | SSE `token` `{text}` | streamed answer text |
| clarify event | SSE `clarify` `{question}` | clarify prompt (stream then ends) |
| done event | SSE `done` `{full AskResponse}` | final payload (answer, code, charts, tables, key_stats, followups, tokens, cost, needs_clarification) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Agent nodes | emit events via `observability/events.py` | fall back to synchronous full response |

## Business Rules
- Single-request SSE endpoint `POST /sessions/{id}/messages/stream` (sse-starlette), consumed by the browser via `fetch` + `ReadableStream`; each node emits a labelled `step` event as it runs. Chosen over a background-run + `GET`-stream design (simpler, single request).
- If the clarify entry-gate triggers, a `clarify` event is emitted and the stream ends without running code.
- The synchronous `POST /sessions/{id}/messages` path returns the same enriched `AskResponse` and remains as a fallback + the test path.

## Success Criteria
- [ ] The stream emits the step labels in order (at least `Planning…`, `Running code…`, `Writing answer…`) before `done`.
- [ ] Answer text arrives as multiple `token` events, not one blob.
- [ ] The `done` event carries the same final answer/code/charts/cost as the synchronous response.
- [ ] A vague question emits a `clarify` event and ends without a `done`-with-answer.
