from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db, Base, engine
from ..models import Setting
from ..schemas import SettingIn, SettingOut


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
    else:
        row = Setting(key=s.key, value=s.value)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

