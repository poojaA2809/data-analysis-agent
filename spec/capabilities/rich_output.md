# Capability: Rich Output (Charts, Tables, Key Stats)

## What It Does
Enriches an answer with an interactive chart, a summary table, and highlighted key statistics derived from the execution result.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| execution_result | JSON | `execute_code` output | yes |
| question | str | user | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| charts | list[chart spec] | answer pane (Plotly/Recharts) |
| tables | list[table spec] | answer pane |
| key_stats | list[stat] | highlighted stat callouts |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Anthropic Claude | choose chart type + which stats to highlight from the result | degrade to plain answer + table only |

## Business Rules
- Charts/tables are built from the already-computed local result — no extra data goes to the LLM beyond the (capped) result summary.
- If the result is not chartable (e.g. a single scalar), only key stats are shown.

## Success Criteria
- [ ] A trend/group-by question yields at least one chart spec and one summary table in the response.
- [ ] Key stats highlight numbers actually present in the result.
- [ ] A scalar-answer question degrades gracefully (key stat only, no broken chart).
