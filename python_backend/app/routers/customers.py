from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import math

from ..database import get_db, Base, engine
from ..models import Customer
from ..schemas import CustomerCreate, CustomerOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/", response_model=str)
def index():
    return "Customers API"


@router.get("/all", response_model=List[CustomerOut])
def list_customers(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(Customer)
    if not include_inactive:
        q = q.filter(Customer.is_active == True)  # noqa: E712
    return q.all()


@router.get("/customer/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@router.post("/customer", response_model=CustomerOut)
def upsert_customer(cust: CustomerCreate, db: Session = Depends(get_db)):
    name = (cust.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Customer name is required")
    if cust.id is not None:
        existing = db.query(Customer).filter(Customer.id == int(cust.id)).first()
        if existing:
            existing.name = name
            existing.phone = cust.phone or ""
            existing.email = cust.email or ""
            existing.address = cust.address or ""
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            newc = Customer(
                id=int(cust.id),
                name=name,
                phone=cust.phone or "",
                email=cust.email or "",
                address=cust.address or "",
            )
            db.add(newc)
            db.commit()
            db.refresh(newc)
            return newc
    else:
        newc = Customer(
            name=name,
            phone=cust.phone or "",
            email=cust.email or "",
            address=cust.address or "",
        )
        db.add(newc)
        db.commit()
        db.refresh(newc)
        return newc


@router.delete("/customer/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    c.is_active = False
    db.add(c)
    db.commit()
    return {"ok": True, "inactive": True}


@router.get("/page", response_model=Dict[str, Any])
def list_customers_page(
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 200))
    q = db.query(Customer)
    if not include_inactive:
        q = q.filter(Customer.is_active == True)  # noqa: E712
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [CustomerOut.model_validate(c).model_dump() for c in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": int(math.ceil(total / float(page_size))) if page_size else 1,
    }
