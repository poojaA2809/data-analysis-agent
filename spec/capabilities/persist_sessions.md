# Capability: Persist Sessions & Conversation History

## What It Does
Persists sessions, datasets, messages, and full run history in SQLite so the user can leave and return (across days) to the same conversation, and injects prior turns as context so follow-up questions are understood.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | str | sidebar selection / active session | yes |
| new question | str | user | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| session bundle | JSON (session, datasets, messages, runs) | `GET /sessions/{id}` → workspace on load |
| session list | JSON | `GET /sessions` → history sidebar |
| conversation context | list[messages] | injected into `plan`/`generate_code` prompts |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | read/write sessions, messages, datasets, runs | surface error; run marked failed if unwritable |

## Business Rules
- All entities persist to disk; nothing is memory-only. A server restart preserves everything.
- Conversation context is truncated to the last N turns to bound the prompt.
- History is never auto-deleted (single-user, full audit trail).

## Success Criteria
- [ ] After restarting the server, `GET /sessions/{id}` returns the prior datasets, messages, and runs.
- [ ] A follow-up question that references the previous turn (e.g. "and by month?") is answered using conversation context (test asserts prior messages present in the prompt).
- [ ] The sidebar lists all sessions ordered by `updated_at`.
