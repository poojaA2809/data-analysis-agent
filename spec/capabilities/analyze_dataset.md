# Capability: Analyze Dataset

## What It Does
Takes a plain-language question about an uploaded dataset, writes and runs Python against it, self-corrects on error until the answer holds (bounded by a step limit), and returns a plain-language answer plus the exact code executed.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | user (question box) | yes |
| dataset_ids | list[str] | user (selected upload) | yes (1 in Phase 1) |
| session_id | str | session context | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text | str | answer pane + `messages` (assistant) |
| generated_code | str | collapsible code panel + `runs.generated_code` |
| run record | Run row | `runs` table (question, plan, code, stdout, result, status, step_count) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Anthropic Claude | plan / codegen / critique / answer (sample rows only) | retry w/ backoff; persistent → run `failed` |
| Local Python executor | run generated pandas in bounded subprocess | error routes to `observe` → retry within step budget |

## Business Rules
- Only the dataset schema + a few sample rows are sent to the LLM; never the full data.
- The code→run→observe→fix loop is bounded by `AGENT_MAX_STEPS` (default 4); on exhaustion, return a best-effort answer flagged low-confidence with what it tried.
- The exact final executed Python is always persisted and shown to the user.
- Execution is time-bounded (`AGENT_EXEC_TIMEOUT`, default 25s) and output-capped.

## Success Criteria
- [ ] A valid question over a real CSV returns a correct plain-language answer in <30s.
- [ ] The `generated_code` returned is the exact code that ran and produced the answer.
- [ ] Given a question whose first generated code raises an error, the agent retries a corrected version and still answers (test asserts `step_count > 1`).
- [ ] The full dataset is never sent to the LLM (asserted: prompt payload size bounded / sample-row count capped).
- [ ] A `runs` row is persisted with question, code, result, and `completed` status.
