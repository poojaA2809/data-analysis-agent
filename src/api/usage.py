from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok
from db.session import get_session
from observability.cost import daily_usage

router = APIRouter()


@router.get("/usage/daily")
def usage_daily(session: Session = Depends(get_session)) -> dict:
    """Running daily token + cost total over today's runs (server-local date)."""
    return ok(daily_usage(session))
