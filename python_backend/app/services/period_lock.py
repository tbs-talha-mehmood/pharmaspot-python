from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Setting


def parse_date_like(raw_value: str) -> Optional[date]:
    txt = str(raw_value or "").strip()
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00")).date()
    except Exception:
        pass
    try:
        normalized = txt.replace("T", " ")
        date_txt = normalized.split()[0] if normalized else ""
        return datetime.strptime(date_txt, "%Y-%m-%d").date()
    except Exception:
        return None


def get_period_lock_until(db: Session) -> Optional[date]:
    row = db.query(Setting).filter(Setting.key == "period_lock_until").first()
    if not row:
        return None
    return parse_date_like(row.value or "")


def ensure_not_locked_for_date(db: Session, target_date: Optional[date], action: str) -> None:
    lock_until = get_period_lock_until(db)
    if lock_until is None or target_date is None:
        return
    if target_date <= lock_until:
        raise HTTPException(
            status_code=423,
            detail=(
                f"{action} is blocked by period lock. "
                f"Locked through {lock_until.isoformat()}."
            ),
        )
