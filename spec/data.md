# Data Model

---

## Storage Technology

**SQLite** (local file at `data/agent.db`) via SQLAlchemy 2.0, migrated with Alembic. Uploaded files are stored on the local filesystem under `data/uploads/`, referenced by path from the `datasets` table. SQLite is the chosen production database for this single-user, local-first tool.

## Entities

### Entity: Session
A conversation with the agent, spanning one or more sittings (persists across days).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| title | str | no | Auto-derived from first question |
| created_at | timestamp | yes | Creation time |
| updated_at | timestamp | yes | Last activity |

### Entity: Dataset
An uploaded file available for analysis in a session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| session_id | str (FK) | yes | Owning session |
| filename | str | yes | Original filename |
| file_path | str | yes | Local path under `data/uploads/` |
| file_type | str | yes | `csv` (P1) / `xlsx` (P2) |
| size_bytes | int | yes | File size |
| profile_json | json/text | no | Auto-profile: columns, types, ranges, quality flags (P2) |
| created_at | timestamp | yes | Upload time |

### Entity: Message
A single chat turn in a session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| session_id | str (FK) | yes | Owning session |
| role | str | yes | `user` / `assistant` |
| content | str | yes | Message text |
| created_at | timestamp | yes | Turn time |

### Entity: Run
One agent execution answering one question (full audit trail).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key (skeleton `RunRow`, extended) |
| session_id | str (FK) | yes | Owning session |
| message_id | str (FK) | no | The assistant message this run produced |
| dataset_ids | json/text | yes | Dataset ids in scope (1 in P1, N in P2) |
| question | str | yes | The user's question |
| plan_json | text | no | Agent plan |
| generated_code | text | no | The exact final Python executed |
| execution_stdout | text | no | Captured stdout |
| result_json | text | no | Row-capped serialized result |
| answer_text | text | no | Plain-language answer |
| status | str | yes | pending / completed / failed |
| step_count | int | yes | Code→fix cycles used |
| prompt_tokens | int | no | LLM usage (P3) |
| completion_tokens | int | no | LLM usage (P3) |
| cost_usd | float | no | Estimated cost (P3) |
| error_message | text | no | On failure |
| created_at | timestamp | yes | Start time |
| completed_at | timestamp | no | End time |

### Relationships

- Session 1—N Dataset, 1—N Message, 1—N Run.
- Run N—1 Message (assistant reply), N references Dataset(s) via `dataset_ids`.

## Data Lifecycle

- **Created:** Session on first interaction; Dataset on upload (file written to disk + row inserted); Message per turn; Run per question.
- **Updated:** Dataset `profile_json` after profiling (P2); Run fields progressively (pending → completed/failed) with metering (P3).
- **Deleted:** No automatic deletion (single-user, keep full history). Manual delete of a session cascades its datasets (files + rows), messages, and runs. Nothing is time-boxed.

## Sensitive Data

The uploaded data may contain PII but stays entirely local — never sent to the LLM in full (only capped sample rows). The Gemini API key lives in `.env` (`AGENT_GEMINI_API_KEY`), never in the DB or client. No auth/secrets stored (single-owner local app).
