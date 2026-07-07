"""Token cost estimation + daily usage aggregation."""
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import get_settings
from db.models import RunRow


def compute_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """USD estimate from token counts using per-Mtok price constants."""
    s = get_settings()
    cost = (
        (prompt_tokens or 0) / 1_000_000 * s.cost_input_per_mtok
        + (completion_tokens or 0) / 1_000_000 * s.cost_output_per_mtok
    )
    return round(cost, 6)


def _local_date(dt: datetime) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date()


def daily_usage(session: Session, day: date | None = None) -> dict:
    """Aggregate token + cost totals over runs created on `day` (server-local
    date, default today). Sums stored values; non-fatal — zeros if none."""
    day = day or datetime.now().astimezone().date()
    runs = session.scalars(select(RunRow)).all()
    prompt_tokens = 0
    completion_tokens = 0
    cost_usd = 0.0
    for r in runs:
        if r.created_at is None or _local_date(r.created_at) != day:
            continue
        prompt_tokens += r.prompt_tokens or 0
        completion_tokens += r.completion_tokens or 0
        cost_usd += r.cost_usd or 0.0
    return {
        "date": day.isoformat(),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost_usd, 6),
    }
