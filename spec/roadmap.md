# Roadmap

---

## What This Agent Does

A personal, local-first data-analysis agent. The owner uploads CSV/Excel files and asks questions in plain language; the agent writes and runs Python against the actual data, then replies with a plain-language answer plus (in later phases) interactive charts, summary tables, and highlighted key stats. It is a code-writing analyst that **plans, then iterates until the answer holds** — write code, run it, observe the result, fix, and retry, bounded by a step limit. It auto-profiles each new upload, suggests smart follow-up questions, and shows the exact code it ran, the tokens/cost per query, and a running daily total. Raw data never leaves the machine; only tiny row samples may be sent to the LLM to aid reasoning.

## Who Uses It

A single technical owner (not multi-tenant), used frequently, in long single-sitting sessions and by returning to the same dataset across multiple days. They want production-quality answers they will act on, with visible trust signals (the code, the cost) and low LLM spend.

## Core Problem Being Solved

Ad-hoc data questions today mean writing throwaway pandas notebooks by hand — slow, repetitive, and easy to get subtly wrong. This agent turns a plain-language question directly into runnable, self-correcting analysis over the user's own files, keeping the data local and the reasoning transparent.

## Success Criteria

- [ ] Uploading a CSV (≤100MB) and asking a plain-language question returns a correct plain-language answer in under 30s on the tested path.
- [ ] The exact Python the agent executed is shown to the user for every answer.
- [ ] When generated code errors, the agent observes the error and retries a corrected version automatically, up to the step limit, without user intervention.
- [ ] Sessions, datasets, messages, and full run history (question, code, answer, timestamps) persist in SQLite and survive a server restart / return-next-day.
- [ ] Every answer displays tokens used and estimated cost, plus a running daily total.
- [ ] Only row samples (a few rows), never the full dataset, are sent to the LLM.

## What This Agent Does NOT Do (Out of Scope)

- No multi-user / multi-tenant accounts, auth, or sharing (single owner, single origin).
- No external data integrations (no databases, warehouses, cloud storage, or SaaS connectors) — files are uploaded manually.
- No writing back to source files or scheduled/automated runs — every analysis is user-triggered.
- No sending raw/full datasets to the LLM — only small row samples.
- No arbitrary internet access from generated code (execution is offline against the local file).
- No fine-tuning or model training.

## Key Constraints

- **Files:** CSV and Excel up to ~100MB.
- **Latency:** answers under 30s on the tested path; code-execution step is time-bounded.
- **Locality:** raw data stays on disk, code runs locally; only a few sample rows may go to the LLM.
- **Cost:** minimize LLM calls; tier models (cheap model for profiling/suggestions, stronger for code). Show cost to the user.
- **Iteration bound:** the code→run→observe→fix loop is capped by `AGENT_MAX_STEPS` (default 4).
- **Stack:** Python + FastAPI + LangGraph + SQLite + Google Gemini (google-genai SDK), extending the repo skeleton in place. Env prefix `AGENT_`, key `AGENT_GEMINI_API_KEY`.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Real backend on the one core path; frontend visually complete with clearly-labelled NON-FUNCTIONAL stubs for everything coming later.

### Phase 1 — Ask-one-CSV

- **Goal:** Upload one CSV → ask one plain-language question → the agent writes and runs Python against the file and returns a plain-language answer, with the exact executed Python shown in a collapsible code panel. Self-correcting: if the code errors, it retries a fix up to the step limit.
- **Independent slices (parallel build units):**
  - `data-migration` (backend) — SQLite schema + Alembic migration for `sessions`, `datasets`, `messages`, `runs`; deps: none.
  - `agent-core` (backend) — LangGraph plan→generate_code→execute_code→observe→finalize loop, local subprocess Python executor, prompts, `analyze_dataset` capability replacing the `transform_text` slot; deps: none (imports the models the migration slice defines — both write disjoint files; declared soft dep on `data-migration` for the model classes, resolved by the shared `src/db/models.py` owned by `data-migration`).
  - `api-routes` (backend) — `POST /datasets` (CSV upload + local storage), `POST /sessions`, `POST /sessions/{id}/messages` (ask → run → answer), `GET /sessions/{id}`; deps: `agent-core`, `data-migration`.
  - `frontend` (frontend) — single-page app: file dropzone (real, CSV only), question box + answer pane (real), collapsible "Code that ran" panel (real), and labelled stubs for charts, cost/token bar, step-stream, follow-ups, multi-file, history; deps: none (talks to the API contract in `spec/api.md`).
  - `e2e` (frontend) — Playwright smoke test of the full upload→ask→answer→open-code-panel journey; deps: `frontend`, `api-routes`.
- **Key surfaces / files:**
  - `data-migration`: `src/db/models.py`, `migrations/` (Alembic), `alembic.ini`.
  - `agent-core`: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/analysis/executor.py`, `src/prompts/*.md`, `tests/`.
  - `api-routes`: `src/api/datasets.py`, `src/api/sessions.py`, `src/domain/*.py`, `src/storage/files.py`.
  - `frontend`: `frontend/src/app/page.tsx`, `frontend/src/app/components/*`.
  - `e2e`: `frontend/tests/e2e/analyze.spec.ts`.
- **Gate command:** `uv run alembic upgrade head` then `uv run pytest` (real Gemini key from `.env`; SQLite is the production DB here). Frontend: `pnpm --dir frontend exec playwright test`.
- **How the user tests it (handoff seed):** Run `uv run uvicorn api.main:app --port 8001` (backend) and build/serve the static frontend at `http://localhost:8001/app/`. Open the app, drag a CSV (e.g. a sales export) into the dropzone, type "What is the average order value by region?", press Ask. Expect: within ~30s a plain-language answer appears; click "Code that ran" to expand the exact pandas the agent executed. Real: CSV upload, the answer, the code panel. Labelled stubs (greyed, "Coming soon"): charts, cost/token bar, live step stream, follow-up chips, multi-file/Excel, session history sidebar.

### Phase 2 — Persist, profile, and combine

- **Goal:** Datasets and full conversation history persist across days; each new upload is auto-profiled (columns, types, ranges, data-quality flags) and shown; the user can load multiple files (including Excel) to join/compare in one question.
- **Capabilities delivered:** `persist_sessions`, `profile_dataset`, `multi_file_analysis`.
- **Independent slices (parallel build units):**
  - `profiling` (backend) — `profile_dataset` node + storage of `profile_json` on upload; deps: none.
  - `persistence` (backend) — session/message/run history read APIs + conversation-history injection into the agent prompt; deps: none.
  - `multi-file` (backend) — Excel loader, multi-dataset selection, executor exposes `dfs[...]` for joins; deps: none.
  - `frontend` (frontend) — history sidebar (real), profile card (real), multi-file picker + Excel upload (real); wires the Phase-1 stubs; deps: none (API contract).
  - `e2e` (frontend) — Playwright: upload→profile shown→ask across two files→reload→history persists; deps: `frontend`.
- **Key surfaces / files:** `profiling`→`src/analysis/profiler.py`, `src/graph/nodes.py`; `persistence`→`src/api/sessions.py`, `src/graph/nodes.py` (history context); `multi-file`→`src/storage/files.py`, `src/analysis/executor.py`, `src/api/datasets.py`; `frontend`→`frontend/src/app/components/*`; `e2e`→`frontend/tests/e2e/persist_profile.spec.ts`.
- **Gate command:** `uv run alembic upgrade head` then `uv run pytest tests/phase2`; frontend `pnpm --dir frontend exec playwright test persist_profile`.
- **How the user tests it (handoff seed):** Upload a CSV and an Excel file; see a profile card per file (columns, types, ranges, quality flags). Ask a question that joins them. Restart the server, reopen the app — the session, both datasets, and the prior Q&A are still there in the sidebar. Real: profile cards, history sidebar, Excel, multi-file join.

### Phase 3 — Rich answers, transparency, and proactivity

- **Goal:** Answers gain interactive charts, summary tables, and highlighted key stats; every query shows tokens/cost plus a running daily total; step updates ("Planning…", "Running code…", "Charting…") and the answer stream in live; the agent suggests 2–3 follow-up questions and, when unsure, asks a clarifying question or gives a flagged best guess with what it tried.
- **Capabilities delivered:** `rich_output`, `cost_transparency`, `live_streaming`, `proactive_assist`.
- **Independent slices (parallel build units):**
  - `rich-output` (backend) — chart/table/keystat spec generation from execution results (`rich_output`); deps: none.
  - `cost-metering` (backend) — per-run token+cost capture and daily-total aggregation API (`cost_transparency`); deps: none.
  - `streaming` (backend) — SSE endpoint emitting step + token events (`live_streaming`); deps: none.
  - `proactive` (backend) — follow-up suggestion + clarify/low-confidence nodes (`proactive_assist`); deps: none.
  - `frontend` (frontend) — chart/table renderers, cost bar + daily total, live step stream + streamed answer, follow-up chips, clarify prompt; deps: none (API contract).
  - `e2e` (frontend) — Playwright: ask→see streamed steps→chart+table render→cost shown→click a follow-up chip; deps: `frontend`.
- **Key surfaces / files:** `rich-output`→`src/analysis/render.py`, `src/graph/nodes.py`; `cost-metering`→`src/observability/cost.py`, `src/api/usage.py`; `streaming`→`src/api/stream.py`, `src/observability/events.py`; `proactive`→`src/graph/nodes.py`, `src/prompts/*.md`; `frontend`→`frontend/src/app/components/*`; `e2e`→`frontend/tests/e2e/rich_stream.spec.ts`.
- **Gate command:** `uv run alembic upgrade head` then `uv run pytest tests/phase3`; frontend `pnpm --dir frontend exec playwright test rich_stream`.
- **How the user tests it (handoff seed):** Ask a question that yields a trend. Watch the step labels stream, then the answer stream in, a chart and summary table render, key stats highlight, and the cost bar show this query's tokens/cost and today's running total. Two–three follow-up chips appear; click one to ask it. Ask a vague question and confirm the agent asks a clarifying question (or gives a flagged best guess showing what it tried).
