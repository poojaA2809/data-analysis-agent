# Capability: Proactive Assist (Follow-ups + Clarify)

## What It Does
After each answer, suggests 2–3 smart follow-up questions; and when the agent is not confident it can answer, it asks a clarifying question first (or gives a flagged best guess showing what it tried and retries a different approach).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | user | yes |
| answer_text / result | str/JSON | finalize | yes (for follow-ups) |
| dataset_schemas | list[dict] | session | yes (for clarify) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| followups | list[str] (2–3) | follow-up chips |
| needs_clarification | str | clarify prompt (question to the user) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini | generate follow-ups | omit chips; answer still shown |
| Google Gemini | assess ambiguity → clarifying question | proceed with best-guess flagged low-confidence |

## Business Rules
- `clarify` runs as an entry gate: if the question is too ambiguous, END with a clarifying question and do not run code.
- If the user proceeds anyway, give a best guess flagged as uncertain, showing what was tried (ties into the step-budget low-confidence path in `analyze_dataset`).
- Follow-ups must be answerable against the current dataset schema.

## Success Criteria
- [ ] Every completed answer includes 2–3 follow-up suggestions.
- [ ] A deliberately vague question ("tell me about it") returns a clarifying question instead of running code.
- [ ] Clicking a follow-up chip submits it as a new question.
