from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime

from ..database import get_db, Base, engine
from ..models import Transaction, Product
from ..schemas import TransactionCreate, TransactionOut, TransactionItem


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/", response_model=str)
def index():
    return "Transactions API"


def _to_dict(t: Transaction) -> TransactionOut:
    items = []
    try:
        raw = json.loads(t.items_json or "[]")
        for it in raw:
            items.append(TransactionItem(id=int(it.get("id")), quantity=int(it.get("quantity", 0))))
    except Exception:
        pass
    return TransactionOut(
        id=t.id,
        date=t.date or "",
        user_id=t.user_id or 0,
        customer_id=t.customer_id or 0,
        till=t.till or 0,
        status=t.status or 1,
        total=t.total or 0.0,
        paid=t.paid or 0.0,
        discount=t.discount or 0.0,
        items=items,
    )


def _compute_profit(items: list[TransactionItem], db: Session) -> float:
    profit = 0.0
    for it in items:
        prod = db.query(Product).filter(Product.id == it.id).first()
        if not prod:
            continue
        try:
            # Use last trade price as proxy for cost
            cost = float(getattr(prod, 'trade_price', 0.0) or 0.0)
            price = float(prod.price or 0.0)
            qty = int(it.quantity or 0)
            profit += (price - cost) * qty
        except Exception:
            pass
    return profit


@router.post("/new", response_model=TransactionOut)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    now = payload.date or datetime.utcnow().isoformat()
    obj = Transaction(
        date=now,
        user_id=payload.user_id or 0,
        customer_id=payload.customer_id or 0,
        till=payload.till or 0,
        status=payload.status or 1,
        total=payload.total or 0.0,
        paid=payload.paid or 0.0,
        discount=payload.discount or 0.0,
        items_json=json.dumps([i.model_dump() for i in payload.items]),
    )
    obj.profit = _compute_profit(payload.items, db)
    db.add(obj)
    # Deduct inventory only if paid >= total and not done before
    should_deduct = (payload.paid or 0.0) >= (payload.total or 0.0)
    if should_deduct and not obj.inventory_deducted:
        for it in payload.items:
            prod = db.query(Product).filter(Product.id == it.id).first()
            if prod and prod.quantity is not None:
                prod.quantity = max(0, int(prod.quantity) - int(it.quantity or 0))
                db.add(prod)
        obj.inventory_deducted = True
    db.commit()
    db.refresh(obj)
    return _to_dict(obj)


@router.get("/list", response_model=List[TransactionOut])
def list_transactions(db: Session = Depends(get_db)):
    rows = db.query(Transaction).all()
    return [_to_dict(t) for t in rows]


@router.put("/transaction/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, payload: TransactionCreate, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # If inventory not yet deducted, check if it should be now
    should_deduct = (payload.paid or 0.0) >= (payload.total or 0.0)
    if should_deduct and not t.inventory_deducted:
        for it in payload.items:
            prod = db.query(Product).filter(Product.id == it.id).first()
            if prod and prod.quantity is not None:
                prod.quantity = max(0, int(prod.quantity) - int(it.quantity or 0))
                db.add(prod)
        t.inventory_deducted = True
    # Update values
    t.user_id = payload.user_id or 0
    t.customer_id = payload.customer_id or 0
    t.till = payload.till or 0
    t.status = payload.status or 1
    t.total = payload.total or 0.0
    t.paid = payload.paid or 0.0
    t.discount = payload.discount or 0.0
    t.items_json = json.dumps([i.model_dump() for i in payload.items])
    t.profit = _compute_profit(payload.items, db)
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


@router.delete("/transaction/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Do not revert stock; assume items already sold. If needed, could add a restock flag here.
    db.delete(t)
    db.commit()
    return {"ok": True}
