"""Pydantic request/response models for the API surface."""
from pydantic import BaseModel


# --- sessions ---
class CreateSessionRequest(BaseModel):
    title: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str | None = None


# --- datasets ---
class DatasetResponse(BaseModel):
    dataset_id: str
    session_id: str
    filename: str
    file_type: str
    size_bytes: int
    profile: dict | None = None


# --- messages / ask ---
class AskRequest(BaseModel):
    question: str
    dataset_ids: list[str]


class AskResponse(BaseModel):
    run_id: str
    status: str
    answer_text: str | None = None
    generated_code: str | None = None
    step_count: int = 0
    needs_clarification: str | None = None
    charts: list = []
    tables: list = []
    key_stats: list = []
    followups: list = []
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    error: str | None = None
