# Capability: Rich Output (Charts, Tables, Key Stats)

## What It Does
Enriches an answer with interactive charts, summary tables, and highlighted key statistics derived from the execution result. Delivered in Phase 3 (a render step in the graph, folded into the finalize stage).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| execution_result | JSON | `execute_code` output | yes |
| question | str | user | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| charts | list of `{type: "bar"\|"line"\|"scatter", title, x_label, y_label, data: [{x, y, series?}]}` | answer pane (recharts, interactive) |
| tables | list of `{title, columns: [str], rows: [[cell,…]]}` | answer pane |
| key_stats | list of `{label, value, delta?}` | highlighted stat callouts (totals, deltas, top movers) |

## External Calls
None required for the render step — charts/tables/key_stats are derived deterministically from the local execution result (`src/analysis/render.py`), no extra LLM call and no extra data sent to the LLM.

## Business Rules
- Charts/tables/key_stats are built from the already-computed local execution result — no extra data goes to the LLM.
- If the result is not chartable (e.g. a single scalar), only key stats are shown (no broken chart).

## Success Criteria
- [ ] A trend/group-by question yields at least one chart spec and one summary table in the response.
- [ ] Key stats highlight numbers actually present in the result.
- [ ] A scalar-answer question degrades gracefully (key stat only, no broken chart).
