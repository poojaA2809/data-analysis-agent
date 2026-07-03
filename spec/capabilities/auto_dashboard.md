# Capability: Auto-Dashboard

## What It Does
From ONE uploaded CSV/dataset, FULLY AUTOMATICALLY (no user question or prompt) generates a visual dashboard representing the data — multiple interactive charts, a summary/aggregation table, 2–5 auto-generated written insights, and a paged/capped data grid of the actual records. Reuses the existing LangGraph agent (plan→generate_code→execute_code→observe→finalize), the local subprocess pandas executor, the Phase-2 profiler, and the Phase-3 render layer (`charts`/`tables`/`key_stats` shapes). Delivered in Phase A (view in-app); export/share follows in Phase B.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | str (uuid) | an already-uploaded dataset row (`POST /datasets`) | yes |

No user question — the agent derives the whole dashboard from the dataset schema + profile + sample rows.

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dashboard | `DashboardPayload` (see below) | dashboard view (reuses recharts renderers + table/grid components) |

**Pinned `DashboardPayload` shape** (reconciled with the Phase-3 chart/table shapes so the frontend reuses its renderers):
```json
{
  "dataset_id": "uuid",
  "title": "Sales export — overview",
  "charts": [
    { "type": "bar" | "line" | "pie" | "scatter",
      "title": "Revenue by region",
      "x_label": "region", "y_label": "revenue",
      "data": [ { "x": "West", "y": 12000, "series": "2026" } ] }
  ],
  "summary_table": { "title": "Totals by region", "columns": ["region", "orders", "revenue"], "rows": [["West", 120, 12000]] },
  "insights": ["West drives 41% of revenue.", "Orders peaked in Q2.", "..."],
  "data_grid": { "columns": ["order_id", "region", "amount"], "rows": [["A1", "West", 99.0]], "total_rows": 5000 }
}
```
- `charts[*]` uses the EXACT Phase-3 chart spec (`{type,title,x_label,y_label,data:[{x,y,series?}]}`), extended with `type: "pie"` (added to `src/analysis/render.py` chart types and the recharts renderer). 2–4 charts across the key columns/relationships.
- `summary_table` is a single object with the Phase-3 table shape (`{title, columns, rows}`) — a grouped-totals / pivot aggregation.
- `insights` is a list of 2–5 short strings (trends, top drivers, outliers, notable stats).
- `data_grid` is the Phase-3 table shape plus `total_rows` — a capped sample of actual records (default cap `AGENT_GRID_ROW_CAP`, e.g. 200) with the full-row count.

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini (`gemini-2.5-flash`, `AGENT_GEMINI_API_KEY`) | plan the dashboard (which columns/relationships to chart), generate pandas for aggregations, write the 2–5 insights | retry w/ backoff in `LLMClient`; on persistent failure the run status → `failed` with a surfaced error |
| Local subprocess pandas executor | run generated aggregation code against the real dataframe (charts data, summary table, data-grid sample) | executor error/timeout routes through `observe` retry loop, bounded by `AGENT_MAX_STEPS` |

Only schema + capped sample rows are sent to Gemini — never the full dataset (same locality rule as the ask path).

## Business Rules
- Fully automatic: no user question/prompt steers generation. The trigger is a dataset id, not a message.
- Reuses the existing agent graph and executor — the dashboard flow is a distinct entry that runs the SAME plan→generate_code→execute_code→observe loop with a dashboard-oriented objective, then a dashboard-finalize that emits the `DashboardPayload`.
- Charts, summary table, and data grid are derived from LOCAL execution results (via the extended `render` layer); only the insights step and the code/plan generation call Gemini.
- Chart types are picked by the agent per column/relationship (categorical→bar/pie, temporal→line, numeric-vs-numeric→scatter); if a relationship is not chartable it is omitted (no broken chart).
- The data grid is capped to `AGENT_GRID_ROW_CAP` rows but reports the true `total_rows`.
- Out of scope (this capability): persistence as saved dashboards, cross-filter slicers, user prompt to steer generation.

## Success Criteria
- [ ] `POST /datasets/{id}/dashboard` on a real multi-column CSV (≥ a few hundred rows, multiple categorical + numeric + a date/temporal column) returns a `DashboardPayload` with ≥2 charts, a non-empty `summary_table`, 2–5 `insights`, and a `data_grid` whose `total_rows` equals the dataset's real row count.
- [ ] At least one chart uses a non-`bar` type where the data warrants it (a temporal column yields a `line`, or a part-of-whole yields a `pie`).
- [ ] The `data_grid.rows` length is ≤ `AGENT_GRID_ROW_CAP` while `total_rows` reflects the full dataset (grid is a capped SAMPLE, aggregations are over the FULL data — a fixture large enough that a sampled vs. full aggregate differ is used in the gate).
- [ ] Every insight references a number/column actually present in the data (no fabricated stats).
- [ ] No user question is required or accepted on this path; the dashboard is produced from the dataset alone.
