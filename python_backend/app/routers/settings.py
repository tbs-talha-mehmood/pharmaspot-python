from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db, Base, engine
from ..models import Setting
from ..schemas import SettingIn, SettingOut, PeriodLockIn, PeriodLockOut
from ..services.period_lock import parse_date_like


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/", response_model=str)
def index():
    return "Settings API"


@router.get("/all", response_model=List[SettingOut])
def list_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()


@router.get("/get", response_model=dict)
def get_all_as_map(db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    return {"settings": {r.key: r.value for r in rows}}


@router.post("/set", response_model=SettingOut)
def set_setting(s: SettingIn, db: Session = Depends(get_db)):
    row = db.query(Setting).filter(Setting.key == s.key).first()
    if row:
        row.value = s.value
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    row = Setting(key=s.key, value=s.value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/period_lock", response_model=PeriodLockOut)
def get_period_lock(db: Session = Depends(get_db)):
    row = db.query(Setting).filter(Setting.key == "period_lock_until").first()
    value = str((row.value if row else "") or "").strip()
    parsed = parse_date_like(value)
    return PeriodLockOut(
        lock_until=parsed.isoformat() if parsed else None,
        locked=parsed is not None,
    )


@router.post("/period_lock", response_model=PeriodLockOut)
def set_period_lock(payload: PeriodLockIn, db: Session = Depends(get_db)):
    raw = str(payload.lock_until or "").strip()
    if not raw:
        row = db.query(Setting).filter(Setting.key == "period_lock_until").first()
        if row:
            row.value = ""
            db.add(row)
            db.commit()
        return PeriodLockOut(lock_until=None, locked=False)

    parsed = parse_date_like(raw)
    if parsed is None:
        raise HTTPException(status_code=400, detail="Invalid lock date. Use YYYY-MM-DD.")

    row = db.query(Setting).filter(Setting.key == "period_lock_until").first()
    if row:
        row.value = parsed.isoformat()
        db.add(row)
    else:
        row = Setting(key="period_lock_until", value=parsed.isoformat())
        db.add(row)
    db.commit()
    return PeriodLockOut(lock_until=parsed.isoformat(), locked=True)
