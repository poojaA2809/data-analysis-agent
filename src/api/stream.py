"""SSE streaming ask endpoint. Emits live step + token events, then a terminal
`done` event carrying the same enriched AskResponse as the synchronous path.
Persists the run identically (reuses graph.runner helpers)."""
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from analysis.schema import derive_schema
from api._common import api_error
from db.models import DatasetRow, MessageRow, SessionRow
from db.session import get_session
from domain.schemas import AskRequest, AskResponse
from graph.agent import agentic_ai
from graph.runner import build_initial_state, create_run_row, persist_run
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.stream")

# node name → user-facing step label (emitted as each node completes).
_STEP_LABELS = {
    "plan": "Planning…",
    "generate_code": "Generating code…",
    "execute_code": "Running code…",
    "observe": "Checking result…",
    "finalize": "Charting…",
}


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


@router.post("/sessions/{session_id}/messages/stream")
def ask_stream(
    session_id: str, req: AskRequest, session: Session = Depends(get_session)
):
    sess = session.get(SessionRow, session_id)
    if sess is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)
    if not req.question or not req.question.strip():
        raise api_error("BAD_REQUEST", "question is required", 400)
    if not req.dataset_ids:
        raise api_error("BAD_REQUEST", "at least one dataset_id is required", 400)

    datasets = []
    for did in req.dataset_ids:
        ds = session.get(DatasetRow, did)
        if ds is None or ds.session_id != session_id:
            raise api_error("BAD_REQUEST", f"Unknown dataset {did}", 400)
        datasets.append(ds)

    user_msg = MessageRow(session_id=session_id, role="user", content=req.question)
    session.add(user_msg)
    if not sess.title:
        sess.title = req.question[:80]

    dataset_paths = [d.file_path for d in datasets]
    dataset_schemas = [derive_schema(d.file_path, d.filename) for d in datasets]

    prior = session.scalars(
        select(MessageRow)
        .where(MessageRow.session_id == session_id)
        .order_by(MessageRow.created_at)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in prior]
    session.commit()

    run_id = create_run_row(session_id, req.question, req.dataset_ids)
    question = req.question

    async def event_gen():
        initial = build_initial_state(
            run_id, session_id, question, dataset_paths, dataset_schemas, history
        )
        merged: dict = dict(initial)
        try:
            for update in agentic_ai.stream(initial, stream_mode="updates"):
                for node_name, delta in update.items():
                    if isinstance(delta, dict):
                        merged.update(delta)
                    label = _STEP_LABELS.get(node_name)
                    if label:
                        yield _sse("step", {"label": label})
                    if node_name == "clarify" and merged.get("needs_clarification"):
                        yield _sse(
                            "clarify", {"question": merged["needs_clarification"]}
                        )
                    if node_name == "finalize":
                        yield _sse("step", {"label": "Writing answer…"})
                        for chunk in _chunk(merged.get("answer_text") or ""):
                            yield _sse("token", {"text": chunk})
        except Exception as exc:  # noqa: BLE001 — surface as failed run, never crash.
            _log.error("stream.error", run_id=run_id, error=str(exc))
            merged.setdefault("status", "failed")
            merged["error"] = merged.get("error") or str(exc)

        payload = persist_run(session_id, run_id, merged)
        yield _sse("done", AskResponse(**payload).model_dump())

    return EventSourceResponse(event_gen())


def _chunk(text: str, size: int = 24):
    """Yield the answer text in small pieces so tokens visibly stream in."""
    words = text.split(" ")
    buf = ""
    for w in words:
        buf = f"{buf} {w}".strip() if buf else w
        if len(buf) >= size:
            yield buf + " "
            buf = ""
    if buf:
        yield buf
