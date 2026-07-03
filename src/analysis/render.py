"""Rich-output rendering: parse the finalize LLM's structured JSON into
charts / tables / key_stats / followups. Never raises — always degrades to an
answer-only payload with empty lists on any parse problem.
"""
import json
import re

_MAX_CHART_POINTS = 200
_MAX_TABLE_ROWS = 100
_MAX_TABLE_COLS = 20
_MAX_KEY_STATS = 8
_MAX_FOLLOWUPS = 3
# "pie" is added for the Phase-A auto-dashboard (part-of-whole charts).
_VALID_CHART_TYPES = {"bar", "line", "pie", "scatter"}

_MIN_INSIGHTS = 2
_MAX_INSIGHTS = 5


def parse_finalize(raw: str) -> dict:
    """Parse the finalize model output. Returns a dict with keys:
    answer (str), charts, tables, key_stats, followups (lists).
    Tolerates prose surrounding the JSON; falls back to answer-only on failure.
    """
    fallback = {
        "answer": (raw or "").strip(),
        "charts": [],
        "tables": [],
        "key_stats": [],
        "followups": [],
    }
    obj = _extract_json(raw)
    if not isinstance(obj, dict):
        return fallback

    answer = obj.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        # Keep the raw prose if the model gave JSON without a usable answer.
        answer = fallback["answer"]

    return {
        "answer": answer.strip(),
        "charts": _clean_charts(obj.get("charts")),
        "tables": _clean_tables(obj.get("tables")),
        "key_stats": _clean_key_stats(obj.get("key_stats")),
        "followups": _clean_followups(obj.get("followups")),
    }


def _extract_json(raw: str):
    if not raw:
        return None
    text = raw.strip()
    # Strip ```json fences if present.
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # Try the whole thing first, then the widest {...} span.
    for candidate in (text, _widest_brace(text)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _widest_brace(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def _clean_charts(charts) -> list:
    if not isinstance(charts, list):
        return []
    out = []
    for c in charts:
        if not isinstance(c, dict):
            continue
        ctype = c.get("type")
        if ctype not in _VALID_CHART_TYPES:
            continue
        raw_data = c.get("data")
        if not isinstance(raw_data, list) or not raw_data:
            continue
        data = []
        for pt in raw_data[:_MAX_CHART_POINTS]:
            if not isinstance(pt, dict) or "x" not in pt or "y" not in pt:
                continue
            point = {"x": pt["x"], "y": pt["y"]}
            if pt.get("series") is not None:
                point["series"] = pt["series"]
            data.append(point)
        if not data:
            continue
        out.append(
            {
                "type": ctype,
                "title": str(c.get("title") or ""),
                "x_label": str(c.get("x_label") or ""),
                "y_label": str(c.get("y_label") or ""),
                "data": data,
            }
        )
    return out


def _clean_tables(tables) -> list:
    if not isinstance(tables, list):
        return []
    out = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        cols = t.get("columns")
        rows = t.get("rows")
        if not isinstance(cols, list) or not cols:
            continue
        cols = [str(c) for c in cols[:_MAX_TABLE_COLS]]
        clean_rows = []
        if isinstance(rows, list):
            for r in rows[:_MAX_TABLE_ROWS]:
                if isinstance(r, list):
                    clean_rows.append([_cell(v) for v in r[: len(cols)]])
        out.append(
            {"title": str(t.get("title") or ""), "columns": cols, "rows": clean_rows}
        )
    return out


def _clean_key_stats(stats) -> list:
    if not isinstance(stats, list):
        return []
    out = []
    for s in stats[:_MAX_KEY_STATS]:
        if not isinstance(s, dict):
            continue
        label = s.get("label")
        value = s.get("value")
        if label is None or value is None:
            continue
        stat = {"label": str(label), "value": _cell(value)}
        if s.get("delta") is not None:
            stat["delta"] = _cell(s["delta"])
        out.append(stat)
    return out


def _clean_followups(followups) -> list:
    if not isinstance(followups, list):
        return []
    out = []
    for f in followups:
        if isinstance(f, str) and f.strip():
            out.append(f.strip())
        if len(out) >= _MAX_FOLLOWUPS:
            break
    return out


def _cell(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


# --- Phase A: auto-dashboard assembly ----------------------------------------

def _clean_single_table(obj) -> dict | None:
    """Clean one summary-table dict via the shared table cleaner."""
    if not isinstance(obj, dict):
        return None
    cleaned = _clean_tables([obj])
    return cleaned[0] if cleaned else None


def clean_insights(insights) -> list:
    """Keep 2–5 non-empty insight strings (capped). May return fewer/zero — the
    caller tops up with derived insights so the payload always has >=2."""
    out: list[str] = []
    if isinstance(insights, list):
        for s in insights:
            if isinstance(s, str) and s.strip():
                out.append(s.strip())
            if len(out) >= _MAX_INSIGHTS:
                break
    return out


def build_data_grid(dataset_path: str, cap: int) -> dict:
    """Deterministic (no LLM) capped SAMPLE of the real records.

    Reads the dataframe, returns all columns, the first `cap` rows as a JSON-safe
    list-of-lists, and the TRUE full row count. Never raises — degrades to empty.
    """
    try:
        import pandas as pd  # local import: render is used LLM-side too

        if dataset_path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(dataset_path)
        else:
            df = pd.read_csv(dataset_path)
        total = int(len(df))
        columns = [str(c) for c in df.columns]
        cap = max(0, int(cap))
        rows = json.loads(df.head(cap).to_json(orient="values", date_format="iso"))
        if not isinstance(rows, list):
            rows = []
        return {"columns": columns, "rows": rows, "total_rows": total}
    except Exception:  # noqa: BLE001 — grid is best-effort
        return {"columns": [], "rows": [], "total_rows": 0}


def parse_dashboard(
    raw_result,
    *,
    dataset_id: str = "",
    title: str = "",
    insights=None,
    data_grid: dict | None = None,
    status: str = "completed",
    error: str | None = None,
) -> dict:
    """Assemble a DashboardPayload from the local execution `raw_result`
    (dict or JSON string with `charts` + `summary_table`), the (LLM or derived)
    `insights`, and the deterministic `data_grid`. Never raises — degrades to
    whatever is valid.
    """
    obj = raw_result if isinstance(raw_result, dict) else _extract_json(raw_result)
    if not isinstance(obj, dict):
        obj = {}

    charts = _clean_charts(obj.get("charts"))
    summary_table = _clean_single_table(obj.get("summary_table")) or {
        "title": "",
        "columns": [],
        "rows": [],
    }
    ins = clean_insights(insights if insights is not None else obj.get("insights"))
    grid = data_grid if isinstance(data_grid, dict) else {
        "columns": [],
        "rows": [],
        "total_rows": 0,
    }

    return {
        "dataset_id": dataset_id,
        "title": title,
        "charts": charts,
        "summary_table": summary_table,
        "insights": ins,
        "data_grid": grid,
        "status": status,
        "error": error,
    }
