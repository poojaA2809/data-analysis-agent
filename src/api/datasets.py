from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import DatasetRow, SessionRow
from db.session import get_session
from domain.schemas import DatasetResponse
from storage.files import store_upload

router = APIRouter()

_MAX_BYTES = 100 * 1024 * 1024  # 100MB


@router.post("/datasets")
async def create_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise api_error("UNSUPPORTED_TYPE", "Only CSV files are supported in Phase 1", 400)

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
    path = store_upload(dataset_id, content, suffix=".csv")

    row = DatasetRow(
        id=dataset_id,
        session_id=session_id,
        filename=filename,
        file_path=path,
        file_type="csv",
        size_bytes=len(content),
        profile_json=None,
    )
    session.add(row)

    return ok(
        DatasetResponse(
            dataset_id=dataset_id,
            session_id=session_id,
            filename=filename,
            file_type="csv",
            size_bytes=len(content),
            profile=None,
        ).model_dump()
    )
