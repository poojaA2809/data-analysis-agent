# Architecture

---

## System Overview

A single-origin local web app. A FastAPI process serves both the REST API and the statically-exported frontend at `http://localhost:8001/app/`. The owner uploads files (stored on local disk), then asks questions in a session. Each question triggers a LangGraph agent run that plans, generates Python, executes it locally against the uploaded dataframe(s) in a bounded subprocess, observes the result, and iterates until the answer holds or the step limit is hit. Sessions, datasets, messages, and runs persist in a local SQLite database. Only tiny row samples are ever sent to Google Gemini; raw data and code execution stay on the machine.

## Component Map

```
Browser (static Next.js export @ /app/)
    ↓  REST + (Phase 3) single-request SSE (POST .../messages/stream)
FastAPI (:8001)  ──►  Google Gemini API (planning / codegen / critique — sample rows only)
    ↓
LangGraph agent (plan → generate_code → execute_code → observe → [retry] → finalize)
    ↓                         ↓
Local Python executor      SQLite (sessions, datasets, messages, runs)
(subprocess, bounded)
    ↓
Local file storage (data/uploads/<dataset_id>.<ext>)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| API (`src/api/`) | HTTP surface: upload, sessions, ask, history, (P3) usage + SSE. Serves `/app/` static export. |
| Agent (`src/graph/`) | LangGraph state machine: plan → codegen → execute → observe → iterate → finalize. |
| Analysis (`src/analysis/`) | Local subprocess Python executor, profiler, (P3) render/keystat extraction. |
| LLM (`src/llm/`) | `LLMClient` wrapper over Google Gemini (skeleton `GeminiProvider`), token/cost capture. |
| Storage (`src/storage/`, `src/db/`) | Local file storage + SQLAlchemy models / SQLite session. |
| Observability (`src/observability/`) | Structured per-run logging, event stream, (P3) cost metering. |

## Data Flow

1. **Trigger:** user uploads a file → `POST /datasets` stores it at `data/uploads/<dataset_id>.<ext>`, records a `datasets` row, and (P2) profiles it.
2. User asks a question in a session → `POST /sessions/{id}/messages` persists the user message and starts a run.
3. Agent **plans** an approach (sample rows + schema in prompt), **generates Python**, **executes it locally** in a bounded subprocess capturing stdout + a `result` value.
4. Agent **observes**: on error or an implausible result it revises the code and retries, up to `AGENT_MAX_STEPS`.
5. **finalize:** compose a plain-language answer and, in Phase 3 (now REAL), a render step derives `charts`/`tables`/`key_stats` from the local execution result and `suggest_followups` proposes 2–3 next questions; token usage from every Gemini call in the run is summed into `prompt_tokens`/`completion_tokens`/`cost_usd`. Persist the `runs` row (question, plan, code, stdout, result, answer, tokens, cost, timestamps) and the assistant message. (Phase 3 also adds a `clarify` entry-gate that can END early with a clarifying question before any code runs.)
6. **Output:** answer + collapsible executed code returned to the browser; Phase 3 (now REAL) streams steps + answer tokens live via the single-request SSE POST and renders interactive charts/tables/key-stats plus per-run + daily cost.
7. **(Phase A) Auto-Dashboard trigger:** after an upload, `POST /datasets/{id}/dashboard` runs the reused agent loop with a dashboard objective and returns a `DashboardPayload` (charts + summary table + insights + capped data grid) — no user question. See the Auto-Dashboard section below.

## Local Python Execution (sandbox model)

Generated code runs in a **fresh child process** (`subprocess.run`, Windows-compatible — no signals), not in the API process:

- The executor writes a runner script that loads the dataset(s) with pandas into `df` (single) / `dfs["<name>"]` (multi), execs the LLM-generated snippet, and prints a JSON envelope `{ "stdout": ..., "result": ..., "error": ... }` where `result` is the value the snippet assigns to a conventional `result` variable (or the last DataFrame/Series/scalar, JSON-serialized with a row cap).
- Bounded by `AGENT_EXEC_TIMEOUT` (default 25s) and an output-size cap; a timeout or non-zero exit is captured as an error the `observe` node can react to.
- Runs with the working dir under `data/uploads/`; no network egress is expected from analysis code. This is a personal, local-first tool — isolation is process + timeout + output-cap, not a hardened multi-tenant sandbox (see out-of-scope in `spec/roadmap.md`).

## Iterate-until-right Loop

Plan-execute + reflection (see `spec/agent.md`). `execute_code` returns a structured observation; `observe` classifies it as *ok* (→ finalize) or *needs-fix* (error, empty, or implausible → back to `generate_code` with the error/critique appended), bounded by `AGENT_MAX_STEPS` (default 4). On exhaustion it finalizes with a best-effort answer flagged as low-confidence including what it tried.

## Database Schema (SQLite)

See `spec/data.md` for full fields. Tables: `sessions`, `datasets` (FK session, holds `file_path`, `file_type`, `profile_json`), `messages` (FK session, role/content), `runs` (FK session + message, holds `question`, `plan_json`, `generated_code`, `execution_stdout`, `result_json`, `answer_text`, `status`, `step_count`, `prompt_tokens`, `completion_tokens`, `cost_usd`, timestamps). Migrations via **Alembic** (`migrations/`), applied with `uv run alembic upgrade head`.

## Streaming (Phase 3)

`POST /sessions/{id}/messages/stream` is a **single-request Server-Sent Events** endpoint (sse-starlette): the ask and the live stream are the same request. The agent emits typed events through `src/observability/events.py` — `step` (`{label: "Planning…"|"Generating code…"|"Running code…"|"Checking result…"|"Charting…"|"Writing answer…"}`), `token` (streamed answer chunks from `finalize`), `clarify` (`{question}`, emitted when the clarify gate triggers, then the stream ends), and `done` (the full enriched `AskResponse`). The synchronous `POST /sessions/{id}/messages` returns the same enriched payload and is used by tests and as a fallback. This POST-stream mechanism is the **chosen design** over a background-run + `GET`-stream (single request, simpler, works with `fetch` + `ReadableStream`). The frontend consumes the stream via `fetch` + `ReadableStream`.

## Auto-Dashboard (Phase A)

`POST /datasets/{id}/dashboard` triggers a FULLY AUTOMATIC dashboard build for ONE dataset — no user question. It reuses the existing agent loop (plan→generate_code→execute_code→observe) with a dashboard objective (which columns/relationships to chart, which aggregations to compute), then a **dashboard-finalize** that assembles the `DashboardPayload` (charts + summary table + 2–5 insights + capped data grid). Charts/summary-table/data-grid are derived from LOCAL execution results via the extended render layer (`src/analysis/render.py` gains a `pie` chart type and dashboard assembly helpers); only plan/codegen and the insights step call Gemini. The data grid is a capped SAMPLE (`AGENT_GRID_ROW_CAP`) while aggregations run over the FULL dataframe and `total_rows` reports the real count. Shapes reconcile with the Phase-3 chart/table specs so the frontend reuses its recharts/table renderers. Trigger is a dataset id (upload path), not the ask path. See [`spec/capabilities/auto_dashboard.md`](capabilities/auto_dashboard.md) and [`spec/agent.md`](agent.md). Phase B adds export/share (image/PDF/shareable file) of the finished dashboard.

## Single-origin Frontend

The Next.js frontend is built with `output: "export"` to static HTML/JS and served by FastAPI under `/app/` (mounted static files). Same origin as the API → no CORS. Dev: `pnpm --dir frontend dev` proxies to `:8001`; production/testing serve the export from `:8001/app/`.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini API | Planning, code generation, critique, answer, (P2) profile summary, (P3) follow-ups | Retry w/ backoff in `LLMClient`; on persistent failure the run status → `failed` with a surfaced error. |
| Local filesystem | Upload storage + executor working dir | Upload/read errors set the run/dataset error and surface to the user. |
| SQLite (local file) | Persistence of all entities | Startup fails fast if the DB is unwritable. |

## Stack

- **Language:** Python 3.12 (backend) + TypeScript (frontend).
- **Agent framework:** LangGraph (extends the repo skeleton).
- **LLM provider + model:** Google Gemini (google-genai SDK). Default `gemini-2.5-flash` for all nodes (plan/codegen/critique/answer/profiling summary/follow-ups). Env-configurable via `AGENT_LLM_MODEL` (default) plus per-node override constants; API key `AGENT_GEMINI_API_KEY`. The provider-agnostic `LLMClient` wrapper (skeleton `GeminiProvider`) keeps the abstraction and captures real `usage_metadata` (`prompt_token_count` / `candidates_token_count`) per call for cost metering (Phase 3). Cost is computed from token counts × per-token price settings `AGENT_COST_INPUT_PER_MTOK` / `AGENT_COST_OUTPUT_PER_MTOK` (defaults set to current `gemini-2.5-flash` pricing). Cheaper-model tiering per node is a future option; the Phase 1 default is a single Gemini model everywhere.
- **Backend:** FastAPI (serves API + static `/app/`).
- **Database + ORM:** SQLite + SQLAlchemy 2.0 (Mapped/DeclarativeBase, per skeleton); Alembic for migrations.
- **Frontend:** Next.js 15 + React 19 (static export) + Tailwind.
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | ^0.2 | Agent state graph |
| google-genai | latest | LLM calls via `LLMClient` |
| pandas | ^2.2 | Dataframe analysis in the executor |
| openpyxl | ^3.1 | Excel loading (Phase 2) |
| sqlalchemy | ^2.0 | ORM |
| alembic | ^1.13 | DB migrations |
| fastapi / uvicorn | latest | API + static serving |
| sse-starlette | ^2 | Single-request SSE streaming (Phase 3) |
| recharts (frontend) | ^2 | Interactive charts/tables rendering (Phase 3; +pie in Phase A) |
| @playwright/test | latest | Frontend E2E |

**Avoid:** heavyweight sandboxing services or remote code runners (local-first, single user); Docker-in-the-loop for execution; sending full datasets to the LLM (sample rows only); PostgreSQL/other DBs (SQLite is the chosen production DB here).

## Deployment Model

A single long-running local process: `uv run uvicorn api.main:app --port 8001`, serving both the REST API and the static frontend at `/app/`. SQLite file and uploads live under `data/`. No cloud deployment.
