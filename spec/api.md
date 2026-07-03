# API

---

## API Style

REST over HTTP (FastAPI), single origin with the static frontend at `/app/`. JSON bodies; file upload is multipart. Phase 3 adds one SSE endpoint. All responses use the skeleton envelope (`ok(...)` / `api_error(...)`).

## Endpoints / Commands

### `POST /datasets` (Phase 1: CSV; Phase 2: + Excel)
**Purpose:** Upload a file, store it locally, create a `datasets` row (P2: auto-profile it).

**Request:** `multipart/form-data` — `session_id` (str, optional; created if absent), `file` (binary).

**Response:**
```json
{ "dataset_id": "uuid", "session_id": "uuid", "filename": "sales.csv",
  "file_type": "csv", "size_bytes": 12345, "profile": null }
```
**Errors:** 400 unsupported type / too large (>100MB); 500 storage failure.

### `POST /sessions`
**Purpose:** Create a session. **Request:** `{ "title": "optional" }`. **Response:** `{ "session_id": "uuid", "title": null }`.

### `POST /sessions/{id}/messages`
**Purpose:** Ask a question — persists the user message, runs the agent, returns the answer + executed code.

**Request:** `{ "question": "average order value by region?", "dataset_ids": ["uuid"] }`

**Response:**
```json
{ "run_id": "uuid", "status": "completed",
  "answer_text": "The average order value is highest in the West…",
  "generated_code": "import pandas as pd\n…",
  "step_count": 2,
  "needs_clarification": null,
  "charts": [], "tables": [], "key_stats": [],
  "followups": [],
  "prompt_tokens": null, "completion_tokens": null, "cost_usd": null }
```
Phase 1 returns `answer_text` + `generated_code` real; `charts/tables/key_stats/followups/*tokens*/cost_usd` are empty/null placeholders wired in later phases.

**Errors:** 400 missing question / unknown dataset; 404 unknown session; 500 run failure (also reflected as `status: "failed"` with `error`).

### `GET /sessions/{id}`
**Purpose:** Load a session with its datasets, messages, and run history (persistence).
**Response:** `{ "session": {...}, "datasets": [...], "messages": [...], "runs": [...] }`.

### `GET /sessions` (Phase 2)
**Purpose:** List sessions for the history sidebar. **Response:** `{ "sessions": [{id, title, updated_at}] }`.

### `GET /usage/daily` (Phase 3)
**Purpose:** Running daily token + cost total. **Response:** `{ "date": "2026-07-03", "prompt_tokens": N, "completion_tokens": N, "cost_usd": 0.12 }`.

### `GET /sessions/{id}/stream/{run_id}` (Phase 3)
**Purpose:** SSE stream of `step`, `token`, and `done` events for a live run. **Response:** `text/event-stream`.

### `GET /health`
Skeleton health check (unchanged).

## Authentication

None — single-owner local app bound to localhost. No tokens or accounts. The Anthropic key is read server-side from `.env`.
