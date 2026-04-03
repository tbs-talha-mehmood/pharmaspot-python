from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from sqlalchemy import func, or_
import math

from ..database import get_db, Base, engine
from ..models import Customer, Transaction
from ..schemas import CustomerCreate, CustomerOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/", response_model=str)
def index():
    return "Customers API"


@router.get("/all", response_model=List[CustomerOut])
def list_customers(include_inactive: bool = False, q: str = "", db: Session = Depends(get_db)):
    query = db.query(Customer)
    if not include_inactive:
        query = query.filter(Customer.is_active == True)  # noqa: E712
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Customer.name).like(needle),
                func.lower(Customer.phone).like(needle),
                func.lower(Customer.email).like(needle),
                func.lower(Customer.address).like(needle),
            )
        )
    return query.all()


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
            if existing.is_active is None or not bool(existing.is_active):
                existing.is_active = True
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
                is_active=True,
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
            is_active=True,
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
    q: str = "",
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 200))
    query = db.query(Customer)
    if not include_inactive:
        query = query.filter(Customer.is_active == True)  # noqa: E712
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Customer.name).like(needle),
                func.lower(Customer.phone).like(needle),
                func.lower(Customer.email).like(needle),
                func.lower(Customer.address).like(needle),
            )
        )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    # Compute per-customer invoice and amount statistics similar to suppliers.
    customer_ids = [int(c.id or 0) for c in rows if int(c.id or 0) > 0]
    stats: dict[int, dict] = {}
    if customer_ids:
        tx_rows = db.query(Transaction).filter(Transaction.customer_id.in_(customer_ids)).all()
        for t in tx_rows:
            cid = int(t.customer_id or 0)
            if cid <= 0:
                continue
            slot = stats.setdefault(
                cid,
                {
                    "invoice_count": 0,
                    "total_sales": 0.0,
                    "total_paid": 0.0,
                    "total_due": 0.0,
                },
            )
            total_amt = max(0.0, float(t.total or 0.0))
            paid_amt = max(0.0, float(t.paid or 0.0))
            due_amt = max(0.0, total_amt - paid_amt)
            slot["invoice_count"] += 1
            slot["total_sales"] += total_amt
            slot["total_paid"] += paid_amt
            slot["total_due"] += due_amt

    items: List[Dict[str, Any]] = []
    for c in rows:
        out = CustomerOut.model_validate(c).model_dump()
        st = stats.get(int(c.id or 0), {})
        out["invoice_count"] = int(st.get("invoice_count", 0) or 0)
        out["total_sales"] = float(st.get("total_sales", 0.0) or 0.0)
        out["total_paid"] = float(st.get("total_paid", 0.0) or 0.0)
        out["total_due"] = float(st.get("total_due", 0.0) or 0.0)
        items.append(out)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": int(math.ceil(total / float(page_size))) if page_size else 1,
    }
