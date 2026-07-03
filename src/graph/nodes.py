"""LangGraph nodes for the analyze_dataset capability.

plan → generate_code → execute_code → observe → [retry] → finalize
Fatal errors route to handle_error.
"""
import json
import re
from pathlib import Path

from analysis.executor import execute_python
from analysis.profiler import profile_dataframe
from config.settings import get_settings
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph.nodes")


def _prompt(name: str) -> str:
    return (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def _schema_block(schemas: list[dict]) -> str:
    """Render dataset schemas + sample rows (sample rows only — never full data)."""
    parts = []
    for s in schemas or []:
        parts.append(
            f"Dataset: {s.get('name')}\n"
            f"Columns (name: dtype): {json.dumps(s.get('columns', {}))}\n"
            f"Sample rows: {json.dumps(s.get('sample_rows', []))}"
        )
    if parts and len(schemas or []) > 1:
        handles = ", ".join(
            f'dfs["{s.get("name")}"]' for s in schemas
        )
        header = (
            f"You have {len(schemas)} datasets loaded. Access each via its handle: "
            f"{handles}. `df` is the first dataset. Join/compare across `dfs[...]`.\n\n"
        )
        return header + "\n\n".join(parts)
    return "\n\n".join(parts) if parts else "(no schema available)"


def _history_block(messages: list | None, max_turns: int = 6) -> str:
    """Render the last N prior conversation turns for context (never full history)."""
    if not messages:
        return ""
    recent = messages[-max_turns:]
    lines = []
    for m in recent:
        role = m.get("role", "user") if isinstance(m, dict) else "user"
        content = m.get("content", "") if isinstance(m, dict) else str(m)
        if content:
            lines.append(f"{role}: {content}")
    if not lines:
        return ""
    return "Prior conversation (most recent turns):\n" + "\n".join(lines) + "\n\n"


def _strip_code_fences(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def plan(state: AgentState) -> AgentState:
    try:
        prompt = (
            f"{_history_block(state.get('messages'))}"
            f"Question: {state['question']}\n\n"
            f"{_schema_block(state.get('dataset_schemas', []))}"
        )
        out = LLMClient().call_model(prompt, system=_prompt("plan"))
        _log.info("node.plan", run_id=state.get("run_id"), plan_len=len(out))
        return {**state, "plan": out}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"plan failed: {exc}"}


def generate_code(state: AgentState) -> AgentState:
    try:
        prompt = (
            f"{_history_block(state.get('messages'))}"
            f"Question: {state['question']}\n\n"
            f"Plan:\n{state.get('plan', '')}\n\n"
            f"{_schema_block(state.get('dataset_schemas', []))}"
        )
        if state.get("execution_error") or state.get("critique"):
            prompt += (
                f"\n\nPrevious code:\n{state.get('generated_code', '')}\n"
                f"\nExecution error: {state.get('execution_error')}\n"
                f"Critique: {state.get('critique')}\n"
                "Fix the problem and produce corrected code."
            )
        out = LLMClient().call_model(prompt, system=_prompt("generate_code"))
        code = _strip_code_fences(out)
        step = state.get("step_count", 0) + 1
        _log.info("node.generate_code", run_id=state.get("run_id"), step=step)
        return {**state, "generated_code": code, "step_count": step}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"generate_code failed: {exc}"}


def execute_code(state: AgentState) -> AgentState:
    result = execute_python(
        state.get("generated_code", ""), state.get("dataset_paths", [])
    )
    _log.info(
        "node.execute_code",
        run_id=state.get("run_id"),
        has_error=bool(result.get("error")),
    )
    return {
        **state,
        "execution_stdout": result.get("stdout") or "",
        "execution_result": json.dumps(result.get("result"), default=str),
        "execution_error": result.get("error"),
    }


def observe(state: AgentState) -> AgentState:
    # An execution error is always needs-fix; still ask the LLM to critique the fix.
    try:
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Code:\n{state.get('generated_code', '')}\n\n"
            f"stdout: {state.get('execution_stdout', '')}\n"
            f"result: {state.get('execution_result', '')}\n"
            f"error: {state.get('execution_error')}"
        )
        out = LLMClient().call_model(prompt, system=_prompt("observe"))
        verdict, notes = _parse_verdict(out)
        # Hard override: a real execution error is never "ok".
        if state.get("execution_error"):
            verdict = "needs-fix"
            notes = notes or state.get("execution_error", "")
        _log.info("node.observe", run_id=state.get("run_id"), verdict=verdict)
        return {**state, "critique": notes, "critique_verdict": verdict}
    except Exception as exc:  # noqa: BLE001
        # Reflection failure is not fatal — default to ok if we have a result.
        verdict = "needs-fix" if state.get("execution_error") else "ok"
        return {**state, "critique": f"observe fallback: {exc}", "critique_verdict": verdict}


def _parse_verdict(text: str) -> tuple[str, str]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            v = obj.get("verdict", "ok")
            return ("needs-fix" if v == "needs-fix" else "ok"), obj.get("notes", "")
        except json.JSONDecodeError:
            pass
    return ("needs-fix" if "needs-fix" in text else "ok"), text.strip()[:200]


def finalize(state: AgentState) -> AgentState:
    try:
        low_conf = (
            state.get("critique_verdict") == "needs-fix"
            and state.get("step_count", 0) >= get_settings().max_steps
        )
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Code:\n{state.get('generated_code', '')}\n\n"
            f"stdout: {state.get('execution_stdout', '')}\n"
            f"result: {state.get('execution_result', '')}"
        )
        if low_conf:
            prompt += (
                "\n\nNote: the step budget was exhausted and this result is "
                "LOW-CONFIDENCE. Explain briefly what was attempted and give the "
                "best-effort answer."
            )
        answer = LLMClient().call_model(prompt, system=_prompt("finalize"))
        _log.info(
            "node.finalize",
            run_id=state.get("run_id"),
            low_confidence=low_conf,
            step_count=state.get("step_count"),
        )
        return {**state, "answer_text": answer, "status": "completed"}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"finalize failed: {exc}"}


def handle_error(state: AgentState) -> AgentState:
    _log.error("node.handle_error", run_id=state.get("run_id"), error=state.get("error"))
    return {**state, "status": "failed"}


def _narrate_profile(profile: dict) -> str | None:
    """Ask Gemini to narrate the deterministic profile. Never raises — returns
    None on any LLM failure so the upload path degrades to deterministic-only."""
    try:
        cols = ", ".join(
            f"{c['name']} ({c['dtype']})" for c in profile.get("columns", [])
        )
        quality = profile.get("quality", {})
        stats = (
            f"Filename: {profile.get('filename')}\n"
            f"Rows: {profile.get('row_count')}, Columns: {profile.get('column_count')}\n"
            f"Columns: {cols}\n"
            f"Missing-value columns: {json.dumps(quality.get('missing_value_columns', []))}\n"
            f"Duplicate rows: {quality.get('duplicate_row_count', 0)}\n"
            f"Outlier columns: {json.dumps(quality.get('outlier_columns', []))}"
        )
        return LLMClient().call_model(stats, system=_prompt("profile"))
    except Exception as exc:  # noqa: BLE001 — narration is best-effort only
        _log.info("profile.narration_skipped", error=str(exc))
        return None


def profile(path: str, filename: str | None = None) -> dict:
    """Upload-path profiler: deterministic stats (source of truth) + optional
    LLM narration. Runs on upload, not on the ask path. Never raises on LLM error.
    """
    prof = profile_dataframe(path, filename)
    narration = _narrate_profile(prof)
    if narration:
        prof["summary"] = narration
    _log.info(
        "node.profile",
        filename=prof.get("filename"),
        row_count=prof.get("row_count"),
        column_count=prof.get("column_count"),
        narrated=bool(narration),
    )
    return prof
