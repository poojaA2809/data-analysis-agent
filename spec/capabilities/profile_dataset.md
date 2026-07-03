# Capability: Auto-Profile a New Upload

## What It Does
On each new upload, computes a profile — columns, inferred types, value ranges/summary stats, and data-quality flags (nulls, duplicates, mixed types) — and shows it so the user knows what they can ask.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset file | file path | upload (`POST /datasets`) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| profile | JSON | `datasets.profile_json` + profile card in UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local (pandas) | compute deterministic profile | profile omitted, upload still succeeds (partial) |
| Anthropic (Haiku) | narrate the profile in one short paragraph | narration omitted; raw stats still shown |

## Business Rules
- Profiling is deterministic (pandas) for the stats; the LLM only narrates — no data values beyond sample rows go to the LLM.
- Runs on the upload path, not the ask path, so it never slows a question.

## Success Criteria
- [ ] Uploading a CSV returns a profile listing every column with a type and a range/summary.
- [ ] At least one data-quality flag (e.g. null count, duplicate rows) is reported when present.
- [ ] The profile is persisted and re-shown when the session is reloaded.
