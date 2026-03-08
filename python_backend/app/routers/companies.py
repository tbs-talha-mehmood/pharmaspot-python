from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
import math

from ..database import get_db, Base, engine
from ..models import Company
from ..schemas import CompanyCreate, CompanyOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/", response_model=str)
def index():
    return "Companies API"


@router.get("/all", response_model=List[CompanyOut])
def list_companies(include_inactive: bool = False, q: str = "", db: Session = Depends(get_db)):
    query = db.query(Company)
    if not include_inactive:
        query = query.filter(Company.is_active == True)  # noqa: E712
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(Company.name).like(needle))
    return query.all()


@router.get("/page", response_model=Dict[str, Any])
def list_companies_page(
    include_inactive: bool = False,
    q: str = "",
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 200))
    query = db.query(Company)
    if not include_inactive:
        query = query.filter(Company.is_active == True)  # noqa: E712
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(Company.name).like(needle))
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [CompanyOut.model_validate(c).model_dump() for c in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": int(math.ceil(total / float(page_size))) if page_size else 1,
    }


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
            if existing.is_active is None or not bool(existing.is_active):
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
