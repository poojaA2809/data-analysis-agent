import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analysis.schema import derive_schema
from api._common import ok, api_error
from db.models import DatasetRow, MessageRow, RunRow, SessionRow
from db.session import get_session
from domain.schemas import (
    AskRequest,
    AskResponse,
    CreateSessionRequest,
    CreateSessionResponse,
)
from graph.runner import run_agent

router = APIRouter()


@router.post("/sessions")
def create_session(
    req: CreateSessionRequest, session: Session = Depends(get_session)
) -> dict:
    row = SessionRow(title=req.title)
    session.add(row)
    session.flush()
    return ok(
        CreateSessionResponse(session_id=row.id, title=row.title).model_dump()
    )


@router.get("/sessions")
def list_sessions(session: Session = Depends(get_session)) -> dict:
    """List sessions for the history sidebar, newest activity first."""
    sessions = session.scalars(
        select(SessionRow).order_by(SessionRow.updated_at.desc())
    ).all()

    def _count(model, sid) -> int:
        return session.scalar(
            select(func.count()).select_from(model).where(model.session_id == sid)
        ) or 0

    return ok(
        {
            "sessions": [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "dataset_count": _count(DatasetRow, s.id),
                    "message_count": _count(MessageRow, s.id),
                }
                for s in sessions
            ]
        }
    )


@router.post("/sessions/{session_id}/messages")
def ask_question(
    session_id: str, req: AskRequest, session: Session = Depends(get_session)
) -> dict:
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

    # Persist the user message.
    user_msg = MessageRow(session_id=session_id, role="user", content=req.question)
    session.add(user_msg)

    # Auto-title the session from the first question.
    if not sess.title:
        sess.title = req.question[:80]

    dataset_paths = [d.file_path for d in datasets]
    dataset_schemas = [derive_schema(d.file_path, d.filename) for d in datasets]

    # Load prior conversation turns for context. autoflush is off, so the
    # just-added (unflushed) user message is not returned here.
    prior = session.scalars(
        select(MessageRow)
        .where(MessageRow.session_id == session_id)
        .order_by(MessageRow.created_at)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in prior]

    # Commit the user message + session before running the agent (separate txn).
    session.commit()

    run_id = run_agent(
        session_id=session_id,
        question=req.question,
        dataset_paths=dataset_paths,
        dataset_schemas=dataset_schemas,
        dataset_ids=req.dataset_ids,
        messages=history,
    )

    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", "Run not found after execution", 500)

    return ok(
        AskResponse(
            run_id=run.id,
            status=run.status,
            answer_text=run.answer_text,
            generated_code=run.generated_code,
            step_count=run.step_count,
            error=run.error_message,
        ).model_dump()
    )


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: str, session: Session = Depends(get_session)
) -> dict:
    sess = session.get(SessionRow, session_id)
    if sess is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    datasets = session.scalars(
        select(DatasetRow).where(DatasetRow.session_id == session_id)
        .order_by(DatasetRow.created_at)
    ).all()
    messages = session.scalars(
        select(MessageRow).where(MessageRow.session_id == session_id)
        .order_by(MessageRow.created_at)
    ).all()
    runs = session.scalars(
        select(RunRow).where(RunRow.session_id == session_id)
        .order_by(RunRow.created_at)
    ).all()

    return ok(
        {
            "session": {
                "id": sess.id,
                "title": sess.title,
                "created_at": sess.created_at.isoformat(),
                "updated_at": sess.updated_at.isoformat(),
            },
            "datasets": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "file_type": d.file_type,
                    "size_bytes": d.size_bytes,
                    "profile": json.loads(d.profile_json) if d.profile_json else None,
                    "created_at": d.created_at.isoformat(),
                }
                for d in datasets
            ],
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
            "runs": [
                {
                    "id": r.id,
                    "question": r.question,
                    "status": r.status,
                    "answer_text": r.answer_text,
                    "generated_code": r.generated_code,
                    "step_count": r.step_count,
                    "created_at": r.created_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in runs
            ],
        }
    )
