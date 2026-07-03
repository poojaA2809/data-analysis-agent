# Agent

---

## Agent Architecture Pattern

**Chosen: Graph (LangGraph)** — a **plan-execute + reflection loop** with **LLM-generated code execution**. The task is multi-step with a conditional retry edge (code → run → observe → fix), which a single deterministic loop cannot express cleanly.

Patterns from `harness/patterns/agentic-ai.md` in use:
- **#6 Planning** — `plan` produces an explicit approach before any code is written.
- **#22 LLM-Generated Code Execution** — `generate_code` + `execute_code`: the LLM writes pandas, the system runs it against the real dataframe. No hardcoded op-list.
- **#4 Reflection** — `observe` critiques the execution result and routes a fix back to `generate_code`.
- **#12 Exception Handling & Recovery** — errors from execution feed the reflection loop; fatal errors route to `handle_error`.
- **#8 Memory Management** — conversation history + prior runs loaded from SQLite (Phase 2).
- **#16 Resource-Aware Optimization** — model tiering (Haiku for profiling/follow-ups, Sonnet for codegen) + sample-rows-only prompts.
- **#13 Human-in-the-Loop** (Phase 3) — `clarify` pauses for a clarifying question on low confidence.
- **#19 Evaluation & Monitoring** — structured per-run logging + token/cost metering (Phase 3).

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| plan | Anthropic | claude-sonnet-4-6 | Reasoning quality on how to answer the question. |
| generate_code | Anthropic | claude-sonnet-4-6 | Correct pandas is the crux; quality over latency. |
| observe / critique | Anthropic | claude-sonnet-4-6 | Judge result plausibility + propose a fix. |
| finalize (answer) | Anthropic | claude-sonnet-4-6 | Clear, act-on-able prose from the result. |
| profile summary (P2) | Anthropic | claude-haiku-4-5-20251001 | Cheap narration of deterministic profile stats. |
| suggest_followups (P3) | Anthropic | claude-haiku-4-5-20251001 | Short, cheap suggestions. |

**Fallback behaviour:** `LLMClient` retries with exponential backoff on transient/rate-limit errors; on persistent failure the node sets `state["error"]` → `handle_error`, run status `failed`, error surfaced. Tests call the real API with `AGENT_ANTHROPIC_API_KEY` from `.env`.

**Prompt strategy:** system prompt per node loaded from `src/prompts/*.md`. Prompts include the dataset **schema + a few sample rows only** (never full data) and, for retries, the prior code + error/critique. Code generation asks for a single Python snippet that assigns a `result` variable. Structured fields (plan steps, critique verdict) requested as compact JSON.

---

## Tools & Tool Calling

The "tool" is the **local Python executor** (not an LLM tool-call; it is a deterministic node the graph invokes with the LLM-generated code).

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `execute_python` (`src/analysis/executor.py`) | Runs generated pandas in a bounded subprocess against the dataset(s) | `code: str`, `dataset_paths: list[str]` | `{stdout, result, error}` | Reads local files; writes none |
| `profile_dataframe` (P2, `src/analysis/profiler.py`) | Deterministic column/type/range/quality profile | `dataset_path: str` | `profile: dict` | none |

**Tool selection strategy:** fixed pipeline — the graph always calls `execute_python` after `generate_code`; no LLM tool-routing.

**Tool failure handling:** executor errors/timeouts are returned as structured observations to `observe`, which decides retry vs. abort within the step budget.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                     # set at initialisation
    session_id: str                 # set at initialisation

    # Input
    question: str                   # user's plain-language question
    dataset_paths: list[str]        # local file paths in scope (1 in P1, N in P2)
    dataset_schemas: list[dict]     # column/type/sample-row info per dataset
    messages: list                  # prior chat turns (P2) — [{role, content}]

    # Pipeline data (populated progressively)
    plan: str                       # plan node output
    generated_code: str             # latest codegen output
    execution_stdout: str           # captured stdout
    execution_result: str           # JSON-serialized result value (row-capped)
    execution_error: str | None     # executor error, if any
    critique: str                   # observe node's verdict/notes
    step_count: int                 # incremented each generate→execute cycle

    # Output
    answer_text: str                # finalize output
    profile: dict                   # P2: auto-profile of a new upload
    charts: list                    # P3: chart specs
    tables: list                    # P3: summary table specs
    key_stats: list                 # P3: highlighted stats
    followups: list[str]            # P3: 2–3 suggested questions
    needs_clarification: str | None # P3: clarifying question, if unsure

    # Metering (P3)
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

    # Control
    error: str | None               # fatal failure → handle_error
    status: str                     # completed | failed
```

---

## Nodes / Steps

Phase-1 REAL nodes: `plan`, `generate_code`, `execute_code`, `observe`, `finalize`, `handle_error`. Phase-2: `profile` (upload path). Phase-3: `suggest_followups`, `clarify`, and rich-output enrichment inside `finalize`.

### `plan`
**Reads:** `question`, `dataset_schemas`, `messages`. **Writes:** `plan`. **LLM:** yes (Sonnet). Produces a short numbered approach for answering the question given the schema + sample rows.

### `generate_code`
**Reads:** `question`, `plan`, `dataset_schemas`, `generated_code`+`execution_error`+`critique` (on retry). **Writes:** `generated_code`, increments `step_count`. **LLM:** yes (Sonnet). Emits one pandas snippet assigning `result`.

### `execute_code`
**Reads:** `generated_code`, `dataset_paths`. **Writes:** `execution_stdout`, `execution_result`, `execution_error`. **LLM:** no. Calls `execute_python` (bounded subprocess).
| System | Operation | On Failure |
|--------|-----------|------------|
| Local subprocess | run generated pandas | capture error/timeout into `execution_error` (partial — loop handles) |

### `observe`
**Reads:** `execution_result`, `execution_error`, `execution_stdout`, `question`. **Writes:** `critique`. **LLM:** yes (Sonnet). Verdict: *ok* → finalize, or *needs-fix* → generate_code (if under step budget).

### `finalize`
**Reads:** `question`, `execution_result`, `execution_stdout`, `generated_code`. **Writes:** `answer_text`, `status="completed"` (P3: `charts`, `tables`, `key_stats`, `followups`). **LLM:** yes (Sonnet answer; Haiku follow-ups). On step-budget exhaustion, writes a best-effort answer flagged low-confidence with what it tried.

### `handle_error`
**Reads:** `error`, `run_id`. **Writes:** `status="failed"`. Updates run row error + timestamp; terminates.

### `profile` (Phase 2)
**Reads:** `dataset_paths`. **Writes:** `profile`. **LLM:** Haiku (narrates deterministic stats from `profile_dataframe`). Runs on the upload path, not the ask path.

### `clarify` (Phase 3)
**Reads:** `question`, `dataset_schemas`. **Writes:** `needs_clarification`. Entry-gate before `plan`: if the question is too ambiguous to answer, emit a clarifying question and END without running code.

---

## Graph / Flow Topology

```
START
  │
  ▼
plan ──(error)──► handle_error ──► END
  │
  ▼
generate_code ──(error)──► handle_error
  │
  ▼
execute_code
  │
  ▼
observe ──(ok)──────────────► finalize ──► END
  │  │
  │  └─(needs-fix & steps<MAX)──► generate_code   (loop)
  │
  └─(needs-fix & steps>=MAX)───► finalize (low-confidence) ──► END

(P3) START ─► clarify ─(ambiguous)─► END(clarifying question)
                     └─(clear)─────► plan
(P2) upload path: START ─► profile ─► END   (separate entry, not the ask graph)
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| plan | `state["error"]` | handle_error |
| generate_code | `state["error"]` | handle_error |
| observe | verdict == ok | finalize |
| observe | verdict == needs-fix and `step_count < MAX_STEPS` | generate_code |
| observe | needs-fix and `step_count >= MAX_STEPS` | finalize |
| clarify (P3) | question ambiguous | END (return clarifying question) |
| clarify (P3) | question clear | plan |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | plan, code, results, critique, step_count |
| Across runs | SQLite (`runs`, `datasets`) | every question, code, answer, profile, timestamps (P2) |
| Conversation | `messages` loaded from SQLite into state (P2) | prior turns for the session, injected into `plan`/`generate_code` prompts |

**Context window management:** never send full data — schema + capped sample rows only; on retries include just the last code + error/critique, not the full history; conversation history truncated to the last N turns.

---

## Human-in-the-Loop Checkpoints

| Checkpoint | Shown to user | Expected action | Default |
|------------|---------------|-----------------|---------|
| `clarify` (Phase 3) | A clarifying question when confidence is low | User replies with specifics | If user proceeds anyway, agent gives a flagged best guess showing what it tried |

---

## Error Handling & Recovery

**Node-level:** each node try/excepts; fatal (non-recoverable) errors set `state["error"]` → `handle_error`. Execution errors are NOT fatal — they route through `observe` into the retry loop.

**Graph-level (handle_error):** reads `error`, `run_id`; sets run status `failed`, `error_message`, `completed_at`; logs with `run_id`; ends.

**Resume / retry strategy:** the code→fix loop is the retry mechanism, bounded by `AGENT_MAX_STEPS` (default 4). No cross-run resume in Phase 1.

**Partial failure:** step-budget exhaustion degrades gracefully to a low-confidence best-effort answer (never a hard crash) that shows the attempts.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Trace | one structured log line per run, one per node (input summary, latency) | stdout structured log (`src/observability/`) |
| LLM calls | prompt/completion tokens, latency, model, cost | structured log + (P3) `runs.prompt_tokens/completion_tokens/cost_usd` |
| Tool calls | executor code (truncated), success/error, latency | structured log |
| Run outcome | status, step_count, total duration, error | `runs` table + structured log |

Structured request/response logging is wired in **Phase 1** (not deferred). No LangSmith dependency required; env `AGENT_LOG_LEVEL` controls verbosity.

---

## Concurrency Model

- **Run isolation:** single-user tool — one run at a time per session; the API executes a run synchronously (P1/P2) and returns the result. `run_id` scopes all writes.
- **Parallel nodes within a run:** none (linear + retry loop).
- **Checkpointing:** none in Phase 1 (runs are short, <30s). Not required — no long pauses except the P3 `clarify` gate, which returns to the client rather than persisting graph state.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("plan", plan)
graph.add_node("generate_code", generate_code)
graph.add_node("execute_code", execute_code)
graph.add_node("observe", observe)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("plan")   # P3: prepend "clarify" as entry with conditional → plan

graph.add_conditional_edges("plan",
    lambda s: "handle_error" if s.get("error") else "generate_code")
graph.add_conditional_edges("generate_code",
    lambda s: "handle_error" if s.get("error") else "execute_code")
graph.add_edge("execute_code", "observe")
graph.add_conditional_edges("observe", route_after_observe,
    {"generate_code": "generate_code", "finalize": "finalize"})
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

agentic_ai = graph.compile()
```

`route_after_observe` (in `src/graph/edges.py`): returns `finalize` if verdict ok or `step_count >= MAX_STEPS`, else `generate_code`.
