# Capabilities Index

> One file per capability — a single discrete thing the agent can do. Extends the skeleton `transform_text` slot, renamed to `analyze_dataset`.

---

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Analyze dataset (plan→code→run→iterate→answer + code panel) | 1 | [analyze_dataset.md](analyze_dataset.md) |
| Persist sessions & conversation history | 2 | [persist_sessions.md](persist_sessions.md) |
| Auto-profile a new upload | 2 | [profile_dataset.md](profile_dataset.md) |
| Multi-file & Excel analysis | 2 | [multi_file_analysis.md](multi_file_analysis.md) |
| Rich output (charts, tables, key stats) | 3 | [rich_output.md](rich_output.md) |
| Cost & token transparency | 3 | [cost_transparency.md](cost_transparency.md) |
| Live streaming step updates | 3 | [live_streaming.md](live_streaming.md) |
| Proactive assist (follow-ups + clarify) | 3 | [proactive_assist.md](proactive_assist.md) |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer creates a new `<name>.md`, updates this index, flags dependencies, and self-reviews.
