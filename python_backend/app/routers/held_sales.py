from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime

from ..database import get_db, Base, engine
from ..models import HeldSale
from ..schemas import HeldSaleCreate, HeldSaleOut, HeldSaleItem


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/held_sales", tags=["held_sales"])


@router.get("/", response_model=str)
def index():
    return "Held Sales API"


def _to_dict(row: HeldSale) -> HeldSaleOut:
    items: list[HeldSaleItem] = []
    try:
        raw = json.loads(row.items_json or "[]")
    except Exception:
        raw = []
    for it in raw or []:
        try:
            pid = int(it.get("product_id", 0) or 0)
            qty = max(0, int(it.get("qty", 0) or 0))
        except Exception:
            continue
        if pid <= 0 or qty <= 0:
            continue
        items.append(
            HeldSaleItem(
                product_id=pid,
                company_id=int(it.get("company_id", 0) or 0),
                retail=float(it.get("retail", 0.0) or 0.0),
                pct=float(it.get("pct", 0.0) or 0.0),
                trade=float(it.get("trade", 0.0) or 0.0),
                extra=float(it.get("extra", 0.0) or 0.0),
                qty=qty,
                label=str(it.get("label", "") or ""),
            )
        )

    return HeldSaleOut(
        id=int(row.id or 0),
        name=str(row.name or ""),
        created=str(row.created or ""),
        customer_id=int(row.customer_id or 0),
        discount=float(row.discount or 0.0),
        paid=float(row.paid or 0.0),
        items=items,
    )


@router.post("/new", response_model=HeldSaleOut)
def create_held_sale(payload: HeldSaleCreate, db: Session = Depends(get_db)):
    rows = []
    for it in payload.items or []:
        try:
            pid = int(it.product_id or 0)
            qty = max(0, int(it.qty or 0))
        except Exception:
            continue
        if pid <= 0 or qty <= 0:
            continue
        rows.append(
            {
                "product_id": pid,
                "company_id": int(it.company_id or 0),
                "retail": float(it.retail or 0.0),
                "pct": float(it.pct or 0.0),
                "trade": float(it.trade or 0.0),
                "extra": float(it.extra or 0.0),
                "qty": qty,
                "label": str(it.label or ""),
            }
        )
    if not rows:
        raise HTTPException(status_code=400, detail="No items to hold")

    created = str(payload.created or "").strip() or datetime.utcnow().isoformat()
    name = str(payload.name or "").strip() or f"Hold {datetime.utcnow().strftime('%H:%M:%S')}"
    obj = HeldSale(
        name=name,
        created=created,
        customer_id=int(payload.customer_id or 0),
        discount=float(payload.discount or 0.0),
        paid=float(payload.paid or 0.0),
        items_json=json.dumps(rows),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _to_dict(obj)


@router.get("/list", response_model=List[HeldSaleOut])
def list_held_sales(db: Session = Depends(get_db)):
    rows = db.query(HeldSale).order_by(HeldSale.id.desc()).all()
    return [_to_dict(r) for r in rows]


@router.delete("/held_sale/{held_sale_id}")
def delete_held_sale(held_sale_id: int, db: Session = Depends(get_db)):
    row = db.query(HeldSale).filter(HeldSale.id == held_sale_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Held sale not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
