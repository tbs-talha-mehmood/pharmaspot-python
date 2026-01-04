from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime

from ..database import get_db, Base, engine
from ..models import Purchase, Product
from ..schemas import PurchaseCreate, PurchaseOut, PurchaseItem


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.get("/", response_model=str)
def index():
    return "Purchases API"


def _to_dict(p: Purchase) -> PurchaseOut:
    items = []
    try:
        raw = json.loads(p.items_json or "[]")
        for it in raw:
            items.append(
                PurchaseItem(
                    product_id=int(it.get("product_id")),
                    company_id=int(it.get("company_id")) if it.get("company_id") is not None else None,
                    quantity=int(it.get("quantity", 0)),
                    price=float(it.get("price", 0.0)),
                    retail_price=float(it.get("retail_price", 0.0)) if it.get("retail_price") is not None else None,
                    discount_pct=float(it.get("discount_pct", 0.0)) if it.get("discount_pct") is not None else None,
                    extra_discount_pct=float(it.get("extra_discount_pct", 0.0)) if it.get("extra_discount_pct") is not None else None,
                    trade_price=float(it.get("trade_price", 0.0)) if it.get("trade_price") is not None else None,
                    is_cut_rate=bool(it.get("is_cut_rate")) if it.get("is_cut_rate") is not None else None,
                )
            )
    except Exception:
        pass
    return PurchaseOut(
        id=p.id,
        date=p.date or "",
        supplier_id=p.supplier_id or 0,
        supplier_name=p.supplier_name or "",
        total=p.total or 0.0,
        items=items,
    )


@router.post("/new", response_model=PurchaseOut)
def create_purchase(payload: PurchaseCreate, db: Session = Depends(get_db)):
    now = payload.date or datetime.utcnow().isoformat()
    obj = Purchase(
        date=now,
        supplier_id=payload.supplier_id or 0,
        supplier_name=payload.supplier_name or "",
        total=payload.total or 0.0,
        items_json=json.dumps([i.model_dump() for i in payload.items]),
    )
    db.add(obj)
    # Increment stock
    for item in payload.items:
        prod = db.query(Product).filter(Product.id == item.product_id).first()
        if prod:
            prod.quantity = int(prod.quantity or 0) + int(item.quantity or 0)
            try:
                prod.cost = float(item.price or 0.0)
            except Exception:
                pass
            db.add(prod)
    db.commit()
    db.refresh(obj)
    return _to_dict(obj)


@router.get("/list", response_model=List[PurchaseOut])
def list_purchases(db: Session = Depends(get_db)):
    items = db.query(Purchase).all()
    return [_to_dict(p) for p in items]


@router.get("/purchase/{purchase_id}", response_model=PurchaseOut)
def get_purchase(purchase_id: int, db: Session = Depends(get_db)):
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return _to_dict(p)


@router.put("/purchase/{purchase_id}", response_model=PurchaseOut)
def update_purchase(purchase_id: int, payload: PurchaseCreate, db: Session = Depends(get_db)):
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    # Revert previous stock
    try:
        prev_items = json.loads(p.items_json or "[]")
    except Exception:
        prev_items = []
    for it in prev_items:
        try:
            prod = db.query(Product).filter(Product.id == int(it.get("product_id"))).first()
            if prod and prod.quantity is not None:
                prod.quantity = max(0, int(prod.quantity) - int(it.get("quantity", 0)))
                db.add(prod)
        except Exception:
            pass

    # Apply new stock increments
    for item in payload.items:
        prod = db.query(Product).filter(Product.id == item.product_id).first()
        if prod:
            prod.quantity = int(prod.quantity or 0) + int(item.quantity or 0)
            try:
                prod.cost = float(item.price or 0.0)
            except Exception:
                pass
            db.add(prod)

    # Update purchase row
    p.supplier_id = payload.supplier_id or 0
    p.supplier_name = payload.supplier_name or ""
    p.total = payload.total or 0.0
    p.items_json = json.dumps([i.model_dump() for i in payload.items])
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_dict(p)


@router.delete("/purchase/{purchase_id}")
def delete_purchase(purchase_id: int, db: Session = Depends(get_db)):
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    # Revert stock increments
    try:
        prev_items = json.loads(p.items_json or "[]")
    except Exception:
        prev_items = []
    for it in prev_items:
        try:
            prod = db.query(Product).filter(Product.id == int(it.get("product_id"))).first()
            if prod and prod.quantity is not None:
                prod.quantity = max(0, int(prod.quantity) - int(it.get("quantity", 0)))
                db.add(prod)
        except Exception:
            pass
    db.delete(p)
    db.commit()
    return {"ok": True}
