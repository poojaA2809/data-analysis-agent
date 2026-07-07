"""DB layer tests — no LLM key required."""
import json

from sqlalchemy.orm import Session

from db.models import SessionRow, DatasetRow, MessageRow, RunRow


def test_session_dataset_message_run_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        sess = SessionRow(title="my session")
        s.add(sess)
        s.flush()
        ds = DatasetRow(
            session_id=sess.id,
            filename="sales.csv",
            file_path="/tmp/x.csv",
            file_type="csv",
            size_bytes=123,
        )
        msg = MessageRow(session_id=sess.id, role="user", content="how many rows?")
        s.add_all([ds, msg])
        s.flush()
        run = RunRow(
            session_id=sess.id,
            message_id=msg.id,
            dataset_ids=json.dumps([ds.id]),
            question="how many rows?",
            status="pending",
            step_count=0,
        )
        s.add(run)
        s.commit()
        sess_id, run_id = sess.id, run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run is not None
        assert run.session_id == sess_id
        assert run.status == "pending"
        assert run.answer_text is None
        assert json.loads(run.dataset_ids)  # dataset ids list survives


def test_run_status_update(_isolated_db):
    with Session(_isolated_db) as s:
        sess = SessionRow()
        s.add(sess)
        s.flush()
        run = RunRow(session_id=sess.id, question="q", status="pending", step_count=0)
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        run.status = "completed"
        run.answer_text = "the answer"
        run.step_count = 2
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "completed"
        assert run.answer_text == "the answer"
        assert run.step_count == 2


def test_ids_are_unique(_isolated_db):
    with Session(_isolated_db) as s:
        ids = []
        for _ in range(3):
            sess = SessionRow()
            s.add(sess)
            s.flush()
            ids.append(sess.id)
        s.commit()
    assert len(set(ids)) == 3
