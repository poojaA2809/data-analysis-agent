# Architecture

---

## System Overview

A single-origin local web app. A FastAPI process serves both the REST API and the statically-exported frontend at `http://localhost:8001/app/`. The owner uploads files (stored on local disk), then asks questions in a session. Each question triggers a LangGraph agent run that plans, generates Python, executes it locally against the uploaded dataframe(s) in a bounded subprocess, observes the result, and iterates until the answer holds or the step limit is hit. Sessions, datasets, messages, and runs persist in a local SQLite database. Only tiny row samples are ever sent to Google Gemini; raw data and code execution stay on the machine.

## Component Map

```
Browser (static Next.js export @ /app/)
    ↓  REST + (Phase 3) SSE
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
5. **finalize:** compose a plain-language answer (P3: + charts/tables/keystats/follow-ups); persist the `runs` row (question, plan, code, stdout, result, answer, tokens, cost, timestamps) and the assistant message.
6. **Output:** answer + collapsible executed code returned to the browser (P3: streamed live via SSE).

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

`GET /sessions/{id}/stream/{run_id}` is a **Server-Sent Events** endpoint. The agent emits typed events through `src/observability/events.py` — `step` (`{label: "Planning…"|"Running code…"|"Charting…"}`), `token` (streamed answer chunks), and `done` (final payload). Phase 1/2 return the full answer synchronously from the POST; Phase 3 wires the SSE stream and the frontend consumes it.

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
- **LLM provider + model:** Google Gemini (google-genai SDK). Default `gemini-2.5-flash` for all nodes (plan/codegen/critique/answer/profiling summary/follow-ups). Env-configurable via `AGENT_LLM_MODEL` (default) plus per-node override constants; API key `AGENT_GEMINI_API_KEY`. The provider-agnostic `LLMClient` wrapper (skeleton `GeminiProvider`) keeps the abstraction. Cheaper-model tiering per node is a future option; the Phase 1 default is a single Gemini model everywhere.
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
| sse-starlette | ^2 | SSE streaming (Phase 3) |
| plotly (frontend: react-plotly / recharts) | — | Interactive charts (Phase 3) |
| @playwright/test | latest | Frontend E2E |

**Avoid:** heavyweight sandboxing services or remote code runners (local-first, single user); Docker-in-the-loop for execution; sending full datasets to the LLM (sample rows only); PostgreSQL/other DBs (SQLite is the chosen production DB here).

## Deployment Model

A single long-running local process: `uv run uvicorn api.main:app --port 8001`, serving both the REST API and the static frontend at `/app/`. SQLite file and uploads live under `data/`. No cloud deployment.
