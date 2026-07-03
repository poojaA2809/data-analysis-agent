"""Runner: create the run row, invoke the graph, persist results + assistant message."""
import json
import time
from datetime import datetime, timezone

from db.models import RunRow, MessageRow, SessionRow
from db.session import create_db_session
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("graph.runner")


def run_agent(
    session_id: str,
    question: str,
    dataset_paths: list[str],
    dataset_schemas: list[dict],
    *,
    dataset_ids: list[str] | None = None,
) -> str:
    """Run the analyze_dataset agent for one question. Returns the run id."""
    started = time.monotonic()

    with create_db_session() as session:
        run = RunRow(
            session_id=session_id,
            question=question,
            dataset_ids=json.dumps(dataset_ids or []),
            status="pending",
            step_count=0,
        )
        session.add(run)
        session.flush()
        run_id = run.id

    _log.info("run.start", run_id=run_id, session_id=session_id, question=question[:120])

    initial: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "question": question,
        "dataset_paths": dataset_paths,
        "dataset_schemas": dataset_schemas,
        "step_count": 0,
        "error": None,
    }

    try:
        final = agentic_ai.invoke(initial)
    except Exception as exc:  # noqa: BLE001 — never crash the request
        final = {"status": "failed", "error": str(exc)}

    status = final.get("status") or ("failed" if final.get("error") else "completed")
    answer = final.get("answer_text")
    now = datetime.now(timezone.utc)

    message_id = None
    with create_db_session() as session:
        if status == "completed" and answer:
            msg = MessageRow(session_id=session_id, role="assistant", content=answer)
            session.add(msg)
            session.flush()
            message_id = msg.id

        run = session.get(RunRow, run_id)
        run.status = status
        run.message_id = message_id
        run.plan_json = final.get("plan")
        run.generated_code = final.get("generated_code")
        run.execution_stdout = final.get("execution_stdout")
        run.result_json = final.get("execution_result")
        run.answer_text = answer
        run.step_count = final.get("step_count", 0)
        run.error_message = final.get("error")
        run.completed_at = now

        # Touch the session's updated_at.
        sess = session.get(SessionRow, session_id)
        if sess is not None:
            sess.updated_at = now

    _log.info(
        "run.done",
        run_id=run_id,
        status=status,
        step_count=final.get("step_count", 0),
        latency_ms=int((time.monotonic() - started) * 1000),
        error=final.get("error"),
    )
    return run_id
