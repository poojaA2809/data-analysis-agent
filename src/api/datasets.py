import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import DatasetRow, SessionRow
from db.session import get_session
from domain.schemas import DatasetResponse
from graph.nodes import profile as profile_upload
from observability.events import get_logger
from storage.files import store_upload

router = APIRouter()

_log = get_logger("api.datasets")

_MAX_BYTES = 100 * 1024 * 1024  # 100MB

# Accepted upload extensions → (file_type, stored suffix).
_ACCEPTED: dict[str, tuple[str, str]] = {
    ".csv": ("csv", ".csv"),
    ".xlsx": ("xlsx", ".xlsx"),
    ".xls": ("xls", ".xls"),
}


def _classify(filename: str) -> tuple[str, str] | None:
    lower = filename.lower()
    for ext, meta in _ACCEPTED.items():
        if lower.endswith(ext):
            return meta
    return None


@router.post("/datasets")
async def create_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    filename = file.filename or "upload.csv"
    meta = _classify(filename)
    if meta is None:
        raise api_error(
            "UNSUPPORTED_TYPE",
            "Only CSV and Excel (.csv, .xlsx, .xls) files are supported",
            400,
        )
    file_type, suffix = meta

    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise api_error("TOO_LARGE", "File exceeds the 100MB limit", 400)
    if len(content) == 0:
        raise api_error("EMPTY_FILE", "Uploaded file is empty", 400)

    # Create the session if none was provided.
    if session_id:
        sess = session.get(SessionRow, session_id)
        if sess is None:
            raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)
    else:
        sess = SessionRow()
        session.add(sess)
        session.flush()
        session_id = sess.id

    dataset_id = str(uuid4())
    path = store_upload(dataset_id, content, suffix=suffix)

    # Auto-profile the upload (deterministic stats + best-effort LLM narration).
    # A profiling failure must NOT block the upload — fall back to no profile.
    profile: dict | None = None
    try:
        profile = profile_upload(path, filename)
    except Exception as exc:  # noqa: BLE001 — upload still succeeds
        _log.error("dataset.profile_failed", dataset_id=dataset_id, error=str(exc))

    row = DatasetRow(
        id=dataset_id,
        session_id=session_id,
        filename=filename,
        file_path=path,
        file_type=file_type,
        size_bytes=len(content),
        profile_json=json.dumps(profile) if profile is not None else None,
    )
    session.add(row)

    return ok(
        DatasetResponse(
            dataset_id=dataset_id,
            session_id=session_id,
            filename=filename,
            file_type=file_type,
            size_bytes=len(content),
            profile=profile,
        ).model_dump()
    )
