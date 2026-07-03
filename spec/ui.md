# UI

---

## UI Type

Single-page web app (Next.js 15 static export served at `http://localhost:8001/app/`). Chat-style analysis workspace for a single owner.

## Views / Screens

### Screen: Analysis Workspace (single page)

**Purpose:** Upload data, ask questions, read answers, and inspect exactly what the agent ran.

**Key elements:**
- **File dropzone** (Phase 1 real, CSV only; Phase 2 adds Excel + multi-file picker) — drag/drop or browse; shows uploaded file chips.
- **Question box** (real) — plain-language input + Ask button.
- **Answer pane** (real) — the plain-language answer for each turn, in a scrolling conversation.
- **Collapsible "Code that ran" panel** (real) — expands to show the exact executed Python per answer.
- **History sidebar** (Phase 1 STUB labelled "Coming soon"; Phase 2 real) — past sessions, click to reload.
- **Profile card** (Phase 1 STUB; Phase 2 real) — per-dataset columns, types, ranges, quality flags.
- **Cost/token bar** (Phase 1 STUB; Phase 3 real) — this query's tokens + cost and today's running total.
- **Live step stream** (Phase 1 STUB; Phase 3 real) — "Planning… / Running code… / Charting…" then streamed answer.
- **Charts + summary tables + key-stat highlights** (Phase 1 STUB; Phase 3 real) — rendered under the answer.
- **Follow-up chips** (Phase 1 STUB; Phase 3 real) — 2–3 suggested next questions.
- **Clarify prompt** (Phase 1 STUB; Phase 3 real) — agent's clarifying question when unsure.

**Actions available:**
- Upload a file; ask a question; expand/collapse the code panel.
- (P2) Select a past session; select multiple datasets for one question.
- (P3) Click a follow-up chip; answer a clarifying question; view daily cost.

**Stub labelling rule:** every not-yet-real surface is visibly greyed with a "Coming soon" badge so a stub is never mistaken for a bug (see `spec/roadmap.md` phase handoffs).

## Error States

- **Upload error** (bad type / >100MB): inline red message on the dropzone.
- **Run failure**: the answer pane shows a clear error card ("The analysis failed: …") rather than a blank.
- **Low-confidence answer** (P3): answer is badge-flagged and shows "what it tried".
- **Loading**: Ask button shows a spinner; Phase 3 replaces it with the live step stream.

## Tech Stack

Next.js 15 + React 19 + TypeScript + Tailwind, static export (`output: "export"`) served by FastAPI at `/app/`. Charts via Plotly/Recharts (Phase 3). E2E via Playwright (`frontend/tests/e2e/`).
