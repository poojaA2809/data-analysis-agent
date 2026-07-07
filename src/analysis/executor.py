"""Local bounded Python executor.

Runs LLM-generated pandas in a FRESH child process (subprocess.run,
Windows-compatible — no signals / os.fork). The child loads the dataset(s)
into `df` (single file) and `dfs["<name>"]` (all files), execs the snippet,
and prints a JSON envelope {"stdout", "result", "error"}.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from config.settings import get_settings

# Cap on serialized result / stdout size returned to the caller.
_MAX_RESULT_ROWS = 200
_MAX_OUTPUT_CHARS = 20000

_RUNNER_TEMPLATE = '''\
import io, json, sys
import contextlib
import pandas as pd

_DATASET_PATHS = {dataset_paths!r}
_MAX_ROWS = {max_rows}


def _load(path):
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def _jsonable(value):
    if isinstance(value, pd.DataFrame):
        return value.head(_MAX_ROWS).to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.head(_MAX_ROWS).to_dict()
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def main():
    envelope = {{"stdout": "", "result": None, "error": None}}
    try:
        dfs = {{}}
        for p in _DATASET_PATHS:
            name = __import__("os").path.splitext(__import__("os").path.basename(p))[0]
            dfs[name] = _load(p)
        df = next(iter(dfs.values())) if dfs else None

        _local = {{"df": df, "dfs": dfs, "pd": pd}}
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            exec(compile({code!r}, "<snippet>", "exec"), _local, _local)
        envelope["stdout"] = _buf.getvalue()

        if "result" in _local:
            envelope["result"] = _jsonable(_local["result"])
        else:
            envelope["result"] = None
    except Exception as exc:  # noqa: BLE001 — capture, never crash
        import traceback
        envelope["error"] = "".join(
            traceback.format_exception_only(type(exc), exc)
        ).strip()
    print("<<<ENVELOPE>>>" + json.dumps(envelope, default=str))


if __name__ == "__main__":
    main()
'''


def execute_python(code: str, dataset_paths: list[str]) -> dict:
    """Run `code` against the datasets in a bounded subprocess.

    Returns {"stdout": str, "result": Any | None, "error": str | None}.
    A timeout or non-zero exit becomes a captured error string, never a crash.
    """
    settings = get_settings()
    script = _RUNNER_TEMPLATE.format(
        dataset_paths=list(dataset_paths),
        code=code,
        max_rows=_MAX_RESULT_ROWS,
    )

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(script)
        tmp.close()
        proc = subprocess.run(
            [sys.executable, tmp.name],
            capture_output=True,
            text=True,
            timeout=settings.exec_timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "result": None,
            "error": f"Execution timed out after {settings.exec_timeout}s",
        }
    except OSError as exc:
        return {"stdout": "", "result": None, "error": f"Executor failed: {exc}"}
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except OSError:
            pass

    stdout = proc.stdout or ""
    marker = "<<<ENVELOPE>>>"
    idx = stdout.rfind(marker)
    if idx == -1:
        # Child crashed before printing the envelope (e.g. import error).
        err = (proc.stderr or "").strip() or "Execution produced no result"
        return {"stdout": stdout[:_MAX_OUTPUT_CHARS], "result": None, "error": err[:_MAX_OUTPUT_CHARS]}

    try:
        envelope = json.loads(stdout[idx + len(marker):])
    except json.JSONDecodeError as exc:
        return {"stdout": "", "result": None, "error": f"Bad executor envelope: {exc}"}

    envelope["stdout"] = (envelope.get("stdout") or "")[:_MAX_OUTPUT_CHARS]
    if isinstance(envelope.get("result"), str):
        envelope["result"] = envelope["result"][:_MAX_OUTPUT_CHARS]
    return envelope
