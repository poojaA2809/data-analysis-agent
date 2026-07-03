"""API contract tests — no LLM key required, the agent graph is not invoked."""
from pathlib import Path

_CSV = Path(__file__).parent.parent / "fixtures" / "sales.csv"


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_create_session(api_client):
    r = api_client.post("/sessions", json={"title": "hello"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["session_id"]
    assert data["title"] == "hello"


def test_upload_csv_creates_session_and_dataset(api_client):
    with _CSV.open("rb") as f:
        r = api_client.post("/datasets", files={"file": ("sales.csv", f, "text/csv")})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["file_type"] == "csv"
    assert data["size_bytes"] > 0
    assert data["profile"] is None
    assert data["session_id"] and data["dataset_id"]


def test_upload_rejects_non_csv(api_client):
    r = api_client.post(
        "/datasets", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert r.status_code == 400


def test_upload_rejects_empty_file(api_client):
    r = api_client.post("/datasets", files={"file": ("empty.csv", b"", "text/csv")})
    assert r.status_code == 400


def test_ask_unknown_session_404(api_client):
    r = api_client.post(
        "/sessions/does-not-exist/messages",
        json={"question": "how many rows?", "dataset_ids": ["x"]},
    )
    assert r.status_code == 404


def test_ask_missing_question_400(api_client):
    s = api_client.post("/sessions", json={}).json()["data"]["session_id"]
    r = api_client.post(
        f"/sessions/{s}/messages", json={"question": "", "dataset_ids": ["x"]}
    )
    assert r.status_code == 400


def test_ask_unknown_dataset_400(api_client):
    s = api_client.post("/sessions", json={}).json()["data"]["session_id"]
    r = api_client.post(
        f"/sessions/{s}/messages",
        json={"question": "how many rows?", "dataset_ids": ["nope"]},
    )
    assert r.status_code == 400


def test_get_session_not_found(api_client):
    r = api_client.get("/sessions/nope")
    assert r.status_code == 404


def test_get_session_returns_shape(api_client):
    s = api_client.post("/sessions", json={"title": "t"}).json()["data"]["session_id"]
    r = api_client.get(f"/sessions/{s}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data.keys()) == {"session", "datasets", "messages", "runs"}
