# Capability: Cost & Token Transparency

## What It Does
Captures tokens and estimated cost per query and shows them alongside a running daily total.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| LLM usage | tokens per call | `LLMClient` responses | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| per-run usage | {prompt_tokens, completion_tokens, cost_usd} | `runs` row + cost bar |
| daily total | {date, tokens, cost_usd} | `GET /usage/daily` → cost bar |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | aggregate today's runs | show last-known/zero; non-fatal |

## Business Rules
- Cost is estimated from token counts using per-model price constants (env-overridable).
- Usage summed across all LLM calls within a run (plan + codegen + critique + answer).
- Daily total is computed from `runs.created_at` for the current local date.

## Success Criteria
- [ ] Each answer response includes non-zero `prompt_tokens`, `completion_tokens`, and `cost_usd`.
- [ ] `GET /usage/daily` returns the sum of today's runs' tokens and cost.
- [ ] The cost bar updates after each query within the same day.
