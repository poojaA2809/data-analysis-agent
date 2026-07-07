# Capability: Multi-File & Excel Analysis

## What It Does
Lets the user load multiple files (including Excel) into one session and ask a single question that joins or compares them.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| files | CSV/XLSX | uploads | yes |
| dataset_ids | list[str] | user (multi-select) | yes (N) |
| question | str | user | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text | str | answer pane |
| generated_code | str | code panel (references `dfs["name"]`) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local (pandas + openpyxl) | load each file into the executor namespace | load error surfaced; run marked failed |
| Google Gemini | plan/codegen over multiple schemas | as in analyze_dataset |

## Business Rules
- Excel loaded via openpyxl; each dataset exposed to generated code as `dfs["<filename>"]`.
- Every selected dataset's schema + sample rows (only) are provided to the LLM.
- File size cap (~100MB) applies per file.

## Success Criteria
- [ ] Uploading an `.xlsx` succeeds and it is queryable.
- [ ] A question joining two datasets returns a correct combined answer (test uses two fixtures with a shared key).
- [ ] The generated code references both datasets via `dfs[...]`.
