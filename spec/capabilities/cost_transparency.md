# Capability: Cost & Token Transparency

## What It Does
Captures real Gemini token usage and estimated cost per query and shows them alongside a running daily total. Delivered in Phase 3.

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
- Token counts come from real Gemini `usage_metadata` (`prompt_token_count` / `candidates_token_count`) on each call.
- Cost = tokens × per-token price from settings `AGENT_COST_INPUT_PER_MTOK` / `AGENT_COST_OUTPUT_PER_MTOK` (defaults set to current `gemini-2.5-flash` pricing, env-overridable).
- Usage summed across ALL LLM calls within a run (clarify + plan + codegen + critique + answer + follow-ups) and persisted on the run (`prompt_tokens`, `completion_tokens`, `cost_usd`).
- Daily total (`GET /usage/daily`) aggregates today's runs for the current local date.

## Success Criteria
- [ ] Each answer response includes non-zero `prompt_tokens`, `completion_tokens`, and `cost_usd`.
- [ ] `GET /usage/daily` returns the sum of today's runs' tokens and cost.
- [ ] The cost bar updates after each query within the same day.
