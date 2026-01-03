from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db, Base, engine
from ..models import Customer
from ..schemas import CustomerCreate, CustomerOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/", response_model=str)
def index():
    return "Customers API"


@router.get("/all", response_model=List[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()


@router.get("/customer/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@router.post("/customer", response_model=CustomerOut)
def upsert_customer(cust: CustomerCreate, db: Session = Depends(get_db)):
    if cust.id is not None:
        existing = db.query(Customer).filter(Customer.id == int(cust.id)).first()
        if existing:
            existing.name = cust.name
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
                name=cust.name,
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
            name=cust.name,
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
    db.delete(c)
    db.commit()
    return {"ok": True}

