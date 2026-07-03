# Capability: Live Streaming Step Updates

## What It Does
Streams the agent's progress ("Planning…", "Running code…", "Charting…") and the final answer to the browser as they happen, over SSE.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| run_id | str | started run | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| step events | SSE `step` | live step indicator |
| token events | SSE `token` | streamed answer text |
| done event | SSE `done` | final payload (code, charts, cost) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Agent nodes | emit events via `observability/events.py` | fall back to synchronous full response |

## Business Rules
- SSE endpoint `GET /sessions/{id}/stream/{run_id}`; each node emits a labelled `step` event on entry.
- The synchronous POST path remains as a fallback if the client does not open the stream.

## Success Criteria
- [ ] The stream emits at least the `Planning…`, `Running code…` steps in order before `done`.
- [ ] Answer text arrives as multiple `token` events, not one blob.
- [ ] The `done` event carries the same final answer/code as the synchronous response.
