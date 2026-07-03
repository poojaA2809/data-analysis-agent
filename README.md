# Data-Analysis Agent — Phase 3 (Rich answers, transparency, and proactivity)

> **Run every command from the repo root.** All Python commands are prefixed with `uv run`.

Upload CSV **and Excel** files, ask plain-language questions, and a LangGraph agent plans,
writes pandas, runs it locally in a bounded subprocess against your real data, self-corrects
on error up to a step limit, and returns a plain-language answer plus the exact executed
Python. Raw data never leaves the machine — only a few sample rows are sent to the LLM.

**Phase 2 adds:** every upload is **auto-profiled** (columns, types, ranges, data-quality
flags) on the upload path; sessions, datasets, messages, and full run history **persist**
across server restarts and are listable for a history sidebar; **conversation memory** injects
prior turns so follow-up questions are understood; and you can load **multiple files (incl.
Excel)** into one session and ask a single question that joins/compares them.

**Phase 3 adds:** answers gain **charts, summary tables, and highlighted key stats** derived
from the execution result (`rich_output`); every query reports **tokens + estimated cost**
plus a **running daily total** (`cost_transparency`, `GET /usage/daily`); a **live SSE stream**
emits step labels and streams the answer text as it is written (`POST
/sessions/{id}/messages/stream`); and the agent suggests **2–3 follow-up questions** and asks a
**clarifying question** when a request is too vague to attempt (`proactive_assist`). The
synchronous `POST /sessions/{id}/messages` returns the SAME enriched payload as the stream.

## Setup & run

```bash
cp .env.example .env          # set AGENT_GEMINI_API_KEY=<your real Gemini key>
uv sync --extra dev

# Build the SQLite schema (sessions, datasets, messages, runs) from scratch:
uv run alembic upgrade head
uv run alembic current        # -> 0001 (head)

# Start the API + static frontend at http://localhost:8001
uv run python -m src
```

Config (env, prefix `AGENT_`): `AGENT_GEMINI_API_KEY`, `AGENT_DATABASE_URL`
(default `sqlite:///./data/agent.db`), `AGENT_MAX_STEPS` (default 4),
`AGENT_EXEC_TIMEOUT` (default 25), `AGENT_LOG_LEVEL`, and cost-metering prices
`AGENT_COST_INPUT_PER_MTOK` (default `0.30`) / `AGENT_COST_OUTPUT_PER_MTOK`
(default `2.50`) — USD per 1M tokens for `gemini-2.5-flash`.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/datasets` | Multipart CSV/Excel upload (`file`, optional `session_id`) → stores under `data/uploads/`, **auto-profiles**, returns `{dataset_id, session_id, filename, file_type, size_bytes, profile}` where `profile` is the deterministic profile dict (see below) |
| POST | `/sessions` | Create a session → `{session_id, title}` |
| POST | `/sessions/{id}/messages` | Ask `{question, dataset_ids}` (N datasets → multi-file join) → runs the agent with conversation memory, returns the **enriched `AskResponse`** (see below) |
| POST | `/sessions/{id}/messages/stream` | Same as above but streams progress live over **SSE** (`text/event-stream`): `step`, `token`, `clarify`, and a terminal `done` event carrying the full `AskResponse` |
| GET | `/usage/daily` | Running daily token + cost total over today's runs (server-local date) → `{date, prompt_tokens, completion_tokens, cost_usd}` |
| GET | `/sessions/{id}` | Session detail → `{session, datasets, messages, runs}`; each dataset carries its real parsed `profile` |
| GET | `/sessions` | List sessions for the history sidebar → `{sessions:[{id, title, created_at, updated_at, dataset_count, message_count}]}` ordered by `updated_at` desc |
| GET | `/health` | Health check |

**Enriched `AskResponse`** (returned by `POST /messages` and inside the SSE `done` event):

```json
{
  "run_id": "uuid", "status": "completed",
  "answer_text": "West leads with a total order value of 400…",
  "generated_code": "import pandas as pd\n…",
  "step_count": 1,
  "needs_clarification": null,
  "charts": [{"type": "bar", "title": "Total order value by region",
              "x_label": "region", "y_label": "total",
              "data": [{"x": "West", "y": 400}, {"x": "East", "y": 350}]}],
  "tables": [{"title": "Totals", "columns": ["region", "total"], "rows": [["West", 400]]}],
  "key_stats": [{"label": "Top region", "value": "West", "delta": "+50"}],
  "followups": ["How do units compare across regions?", "What is the trend over time?"],
  "prompt_tokens": 1234, "completion_tokens": 210, "cost_usd": 0.000895,
  "error": null
}
```

When the clarify entry-gate fires on a vague question, `status` is `"needs_clarification"`,
`needs_clarification` holds the clarifying question, and no code runs (`generated_code` null,
`step_count` 0). Chart types are `bar` | `line` | `scatter`; a scalar answer degrades to
`key_stats` only (empty `charts`).

**SSE event shapes** (`POST /sessions/{id}/messages/stream`, one JSON object per `data:` line):

```
event: step     data: {"label": "Planning…"}          # also: Generating code…, Running code…, Checking result…, Charting…, Writing answer…
event: token    data: {"text": "West leads with "}     # answer prose, streamed in chunks
event: clarify  data: {"question": "Which metric…?"}    # only on the vague-question gate
event: done     data: { …full AskResponse json… }       # terminal event
```

**Profile shape** (`profile` field on `POST /datasets` and each `datasets[]` in `GET /sessions/{id}`):

```json
{
  "filename": "sales.csv",
  "row_count": 6,
  "column_count": 3,
  "summary": "Optional one-paragraph LLM narration (omitted if the LLM errors).",
  "columns": [
    {"name": "order_value", "dtype": "int64", "non_null_count": 6, "null_count": 0,
     "null_pct": 0.0, "unique_count": 6, "is_numeric": true,
     "summary": {"mean": 175.0, "std": 93.5, "min": 50.0, "max": 300.0},
     "outlier_count": 0},
    {"name": "region", "dtype": "object", "non_null_count": 6, "null_count": 0,
     "null_pct": 0.0, "unique_count": 3, "is_numeric": false,
     "top_values": [{"value": "West", "count": 3}]}
  ],
  "quality": {
    "missing_value_columns": [{"name": "order_value", "null_count": 1, "null_pct": 20.0}],
    "duplicate_row_count": 1,
    "outlier_columns": [{"name": "amount", "outlier_count": 2}]
  }
}
```

Multi-file: generated code accesses each dataset via `dfs["<filename-stem>"]` (and `df` = the
first dataset). Excel is loaded via `openpyxl`. Profiling is deterministic (pandas) — the
deterministic dict is the source of truth; the optional `summary` narration is best-effort and
the upload never fails if the LLM errors.

### Tests

```bash
uv run pytest tests/unit/ -q         # no key needed (contract, DB, executor, settings)
uv run pytest tests/phase2/ -q       # Phase 2: profiler (no key) + integration (needs key)
uv run pytest -q                     # full suite — integration needs a real AGENT_GEMINI_API_KEY
```

Integration tests hit the real Google Gemini API (model `gemini-2.5-flash`) and a real
subprocess pandas executor; they skip only if no key is present.

---

# Zero Shot SDD Harness for Building Agents

Give it a one-line idea. Walk away with a working, tested, phased agent.

A lean, Claude-Code-native harness for building agentic software **spec-first**. One person with an idea and one API key can drive a real, production-shaped agent into existence — and a senior engineer opening the result finds a conventional, reviewable stack, not generated mush.

---

## The Spirit

Six convictions the whole repo is built around:

1. **Spec is the source of truth.** The spec is written before the code, always. When spec and code disagree, the spec wins and the code is fixed (`/zero-shot-sync`). Every AI session reads the same requirements instead of re-deriving them.
2. **Built for two audiences at once.** A non-coder drives it with a single sentence; a senior engineer inherits a clean FastAPI + LangGraph stack they can read, review, and own. Neither audience is an afterthought.
3. **Lean harness, not a framework.** `harness/` is engineering *mindfulness* — rules and patterns that keep every session consistent — deliberately Claude-Code-only and kept small. The product runtime stays provider-agnostic; the harness does not.
4. **Smallest first-time-right win, phase by phase.** Each phase ships the smallest increment a human can actually test, and it must work the *first* time they test it — real on the tested path, with clearly-labelled stubs for everything still to come. No rough edges on the path you're handed.
5. **A human gates every phase.** The build is autonomous *within* a phase and stops at each boundary for you to test the increment. You stay in control of what "done" means.
6. **Real LLM/API or it doesn't count.** Gates, tests, and evals run against the real model with keys from `.env`. A stubbed pass is not a pass.

---

## What This Is

A starting point for building AI agents spec-first. The repo ships with:

- A working **baseline agent** in `src/` (FastAPI + LangGraph + SQLite, provider-agnostic LLM — Anthropic or Gemini, `transform_text` as the capability slot) — tests pass out of the box
- A **spec template** in `spec/` covering roadmap, architecture, capabilities, data model, API, UI, and agent graph
- Three **zero-shot skills** (`/zero-shot-build`, `/zero-shot-fix`, `/zero-shot-sync`)
- A four-agent **team** — agent-builder orchestrates (plans, fans out, owns git/PR); spec-writer is the single design authority; code-generator implements one slice per instance (parallelised); qa-auditor reviews and gates
- Engineering rules and patterns in `harness/` so every Claude Code session is consistent
- **Human testing gate between phases** — autonomous within a phase, you test each increment before the next starts

---

## How to Use This

### Step 1 — Clone

```bash
git clone https://github.com/smallTechOrg/zero-shot-sdd-harness.git my-agent
cd my-agent
```

### Step 2 — Open in Claude Code

```bash
claude
```

### Step 3 — Build

```
/zero-shot-build An agent that monitors my Shopify store for low-inventory products and drafts restock emails to suppliers
```

One intake round (scope, stack, API keys → fill `.env`), then the agent builds phase by phase and stops at each boundary for you to test.

---

## What Happens (Intake → Phase by Phase)

```
Your idea
    ↓
INTAKE — scope, stack, LLM provider, constraints; fill .env with the required API key
    ↓
[spec-writer]  → Full spec: architecture + agent-graph + phased plan (self-reviewed)
    ↓
[agent-builder] → Feature branch + PR, scaffold
    ↓
per phase — all slices concurrently:
    [code-generator: slice-a]  ──→  [qa-auditor: slice-a]  ─┐
    [code-generator: slice-b]  ──→  [qa-auditor: slice-b]  ─┤→  commit + push
    [code-generator: slice-c]  ──→  [qa-auditor: slice-c]  ─┘
    ↓
HUMAN TESTING GATE — exact run commands + expected result; you confirm before next phase
    ↓
(issue → qa-auditor classifies SPEC-vs-CODE → code-generator fixes → re-gate)
    ↓
repeat per phase → SHIP
```

Phase 1 is the smallest first-time-right win — real on the tested path, with labelled stubs for everything coming later. Each later phase wires one more stub into real functionality.

---

## Repo Layout

```
src/                ← baseline agent (FastAPI + LangGraph + SQLite, Anthropic/Gemini)
  api/              ← FastAPI routers (create_app, health, runs)
  config/           ← Pydantic BaseSettings
  db/               ← SQLAlchemy models + session
  domain/           ← Pydantic request/response models
  graph/            ← LangGraph nodes, edges, state, runner  ← CAPABILITY SLOT
  llm/              ← LLM client + providers/ (anthropic, gemini)
  prompts/          ← prompt templates (.md)
  observability/
frontend/           ← Next.js static export (served by FastAPI at /app)
tests/
  unit/             ← passes with no API key
  integration/      ← requires real key in .env
spec/               ← your spec: roadmap, architecture, capabilities/, data, api, ui, agent
harness/
  rules/            ← ai-agents, git, secret-hygiene
  patterns/         ← spec-driven, phases, project-layout, tech-stack, code, test-driven, ui-ux, agentic-ai, engineering-practices
.claude/
  skills/           ← /zero-shot-build, /zero-shot-fix, /zero-shot-sync
  agents/           ← agent-builder, spec-writer, code-generator, qa-auditor
CLAUDE.md
pyproject.toml
alembic.ini        ← Alembic migrations (alembic/)
agent.py            ← verify setup (default); --run to start the server
.env.example
```

**Capability slot** — the three files to replace for your agent:
- `src/graph/nodes.py` — replace `transform_text` with your logic
- `src/prompts/transform.md` — replace with your system prompt
- `frontend/src/app/page.tsx` — replace the transform form with your UI

Everything else (graph wiring, API, DB, settings, tests) is already working.

---

## Running the Baseline

```bash
cp .env.example .env
# edit .env: set exactly ONE provider key —
#   AGENT_ANTHROPIC_API_KEY=<your key>   or   AGENT_GEMINI_API_KEY=<your key>
# the provider is auto-detected from whichever key is set
uv sync
python agent.py                        # verify tools, .env, deps, tests (default)
python agent.py --run                  # migrations + frontend build + start server
```

Once running:

| URL | What |
|-----|------|
| `http://localhost:8001/app/` | **UI** — transform form (the capability slot) |
| `http://localhost:8001/health` | API health check |
| `http://localhost:8001/docs` | Interactive API docs (Swagger) |

Tests:

```bash
uv run pytest tests/unit/ -v          # no key needed
uv run pytest tests/ -v               # requires real key in .env
```

---

## Rules AI Agents Follow

Full rules in `harness/rules/ai-agents.md`. Summary:

- Read the full spec before writing any code
- Never skip a phase; commit every logical unit
- Tests run against the real LLM/API using keys from `.env` — stubbed runs do not count as passing
- Each phase is tested by the human before the next phase starts
- The build record is git history + the PR + the per-phase test-handoffs

---

## FAQ

**What if I already have a stack in mind?**
State it in the idea: `/zero-shot-build [idea] — use Python + FastAPI + PostgreSQL`. Stack choices are binding.

**What if something breaks?**
Run `/zero-shot-fix [what's broken]` — qa-auditor classifies the problem (SPEC vs CODE), the right generator fixes it, qa-auditor re-gates.

**What if spec and code drift?**
Run `/zero-shot-sync` — qa-auditor classifies each divergence, generators fix, spec wins.
