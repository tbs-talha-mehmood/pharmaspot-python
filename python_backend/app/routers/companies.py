from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from ..database import get_db, Base, engine
from ..models import Company
from ..schemas import CompanyCreate, CompanyOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/", response_model=str)
def index():
    return "Companies API"


@router.get("/all", response_model=List[CompanyOut])
def list_companies(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(Company)
    if not include_inactive:
        q = q.filter(Company.is_active == True)  # noqa: E712
    return q.all()


@router.post("/company", response_model=CompanyOut)
def upsert_company(c: CompanyCreate, db: Session = Depends(get_db)):
    name = (c.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Company name is required")
    name_l = name.lower()
    if c.id is not None:
        existing = db.query(Company).filter(Company.id == int(c.id)).first()
        if existing:
            conflict = db.query(Company).filter(func.lower(Company.name) == name_l, Company.id != int(c.id)).first()
            if conflict:
                raise HTTPException(status_code=400, detail="Company name already exists")
            existing.name = name
            if existing.is_active is None:
                existing.is_active = True
            db.add(existing)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(status_code=400, detail="Company name already exists")
            db.refresh(existing)
            return existing
        else:
            conflict = db.query(Company).filter(func.lower(Company.name) == name_l).first()
            if conflict:
                raise HTTPException(status_code=400, detail="Company name already exists")
            newc = Company(id=int(c.id), name=name, is_active=True)
            db.add(newc)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(status_code=400, detail="Company name already exists")
            db.refresh(newc)
            return newc
    else:
        conflict = db.query(Company).filter(func.lower(Company.name) == name_l).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Company name already exists")
        newc = Company(name=name, is_active=True)
        db.add(newc)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Company name already exists")
        db.refresh(newc)
        return newc


@router.delete("/company/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    obj = db.query(Company).filter(Company.id == company_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Company not found")
    obj.is_active = False
    db.add(obj)
    db.commit()
    return {"ok": True, "inactive": True}
