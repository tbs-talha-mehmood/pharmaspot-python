from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
import math

from ..database import get_db, Base, engine
from ..models import Supplier
from ..schemas import SupplierCreate, SupplierOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("/", response_model=str)
def index():
    return "Suppliers API"


@router.get("/all", response_model=List[SupplierOut])
def list_suppliers(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(Supplier)
    if not include_inactive:
        q = q.filter(Supplier.is_active == True)  # noqa: E712
    return q.all()


@router.get("/page", response_model=Dict[str, Any])
def list_suppliers_page(
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 200))
    q = db.query(Supplier)
    if not include_inactive:
        q = q.filter(Supplier.is_active == True)  # noqa: E712
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [SupplierOut.model_validate(s).model_dump() for s in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": int(math.ceil(total / float(page_size))) if page_size else 1,
    }


@router.post("/supplier", response_model=SupplierOut)
def upsert_supplier(s: SupplierCreate, db: Session = Depends(get_db)):
    name = (s.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Supplier name is required")
    name_l = name.lower()
    if s.id is not None:
        existing = db.query(Supplier).filter(Supplier.id == int(s.id)).first()
        if existing:
            conflict = db.query(Supplier).filter(func.lower(Supplier.name) == name_l, Supplier.id != int(s.id)).first()
            if conflict:
                raise HTTPException(status_code=400, detail="Supplier name already exists")
            existing.name = name
            if existing.is_active is None:
                existing.is_active = True
            db.add(existing)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(status_code=400, detail="Supplier name already exists")
            db.refresh(existing)
            return existing
        conflict = db.query(Supplier).filter(func.lower(Supplier.name) == name_l).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Supplier name already exists")
        news = Supplier(id=int(s.id), name=name, is_active=True)
        db.add(news)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Supplier name already exists")
        db.refresh(news)
        return news

    conflict = db.query(Supplier).filter(func.lower(Supplier.name) == name_l).first()
    if conflict:
        raise HTTPException(status_code=400, detail="Supplier name already exists")
    news = Supplier(name=name, is_active=True)
    db.add(news)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Supplier name already exists")
    db.refresh(news)
    return news


@router.delete("/supplier/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    obj = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Supplier not found")
    obj.is_active = False
    db.add(obj)
    db.commit()
    return {"ok": True, "inactive": True}
