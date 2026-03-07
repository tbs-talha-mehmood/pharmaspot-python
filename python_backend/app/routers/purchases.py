from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from sqlalchemy import func
import json
from datetime import datetime
import math

from ..database import get_db, Base, engine
from ..models import Purchase, Product, Supplier
from ..schemas import PurchaseCreate, PurchaseOut, PurchaseItem
from ..services.period_lock import ensure_not_locked_for_date, parse_date_like
from ..services.cogs import rebuild_and_persist_cogs_allocations


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


def _normalize_supplier(supplier_id: int | None, supplier_name: str | None) -> tuple[int, str]:
    try:
        sid = int(supplier_id or 0)
    except Exception:
        sid = 0
    sname = str(supplier_name or "").strip()
    if sid <= 0 and not sname:
        raise HTTPException(status_code=400, detail="Supplier is required")
    return sid, sname


def _resolve_supplier(db: Session, supplier_id: int | None, supplier_name: str | None) -> tuple[int, str]:
    sid, sname = _normalize_supplier(supplier_id, supplier_name)
    if sid > 0:
        row = db.query(Supplier).filter(Supplier.id == int(sid)).first()
        if row:
            if row.is_active is None or not bool(row.is_active):
                row.is_active = True
                db.add(row)
            return int(row.id or 0), str(row.name or sname or "").strip()
        if not sname:
            raise HTTPException(status_code=400, detail="Supplier not found")
        # Create with provided ID only if it does not already exist.
        new_row = Supplier(id=int(sid), name=str(sname).strip(), is_active=True)
        db.add(new_row)
        try:
            db.flush()
            return int(new_row.id or 0), str(new_row.name or "").strip()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=400, detail="Supplier could not be created")

    # sid <= 0 with typed name
    name_l = str(sname).strip().lower()
    existing = db.query(Supplier).filter(func.lower(Supplier.name) == name_l).first()
    if existing:
        if existing.is_active is None or not bool(existing.is_active):
            existing.is_active = True
            db.add(existing)
        return int(existing.id or 0), str(existing.name or sname or "").strip()
    new_row = Supplier(name=str(sname).strip(), is_active=True)
    db.add(new_row)
    db.flush()
    return int(new_row.id or 0), str(new_row.name or "").strip()


def _sync_purchase_item_pricing(prod: Product, item: PurchaseItem) -> None:
    # Update retail price if provided
    try:
        if item.retail_price is not None:
            prod.price = float(item.retail_price or 0.0)
    except Exception:
        pass
    # Derive discount if missing using retail/trade when available
    discount_val = item.discount_pct
    if discount_val is None:
        try:
            retail_val = float(item.retail_price or 0.0)
            trade_val = float(item.trade_price if item.trade_price is not None else item.price or 0.0)
            if retail_val > 0:
                discount_val = max(0.0, (1.0 - (trade_val / retail_val)) * 100.0)
        except Exception:
            discount_val = None
    if discount_val is not None:
        try:
            prod.discount_pct = float(discount_val or 0.0)
        except Exception:
            pass
    try:
        # Keep trade as pre-extra discount amount when available.
        trade_val = item.trade_price
        if trade_val is None:
            trade_val = item.price
        prod.trade_price = float(trade_val or 0.0)
    except Exception:
        pass


def _aggregate_qty_from_raw_items(raw_items: list[dict]) -> dict[int, int]:
    out: dict[int, int] = {}
    for it in raw_items or []:
        try:
            pid = int(it.get("product_id", 0) or 0)
            qty = max(0, int(it.get("quantity", 0) or 0))
        except Exception:
            continue
        if pid <= 0 or qty <= 0:
            continue
        out[pid] = int(out.get(pid, 0) or 0) + qty
    return out


def _aggregate_qty_from_payload(items: list[PurchaseItem]) -> dict[int, int]:
    out: dict[int, int] = {}
    for it in items or []:
        try:
            pid = int(it.product_id or 0)
            qty = max(0, int(it.quantity or 0))
        except Exception:
            continue
        if pid <= 0 or qty <= 0:
            continue
        out[pid] = int(out.get(pid, 0) or 0) + qty
    return out


def _apply_quantity_delta(db: Session, delta_by_pid: dict[int, int]) -> None:
    products: dict[int, Product] = {}
    for pid in delta_by_pid.keys():
        prod = db.query(Product).filter(Product.id == int(pid)).first()
        if not prod:
            raise HTTPException(status_code=400, detail=f"Product not found: {int(pid)}")
        if prod.quantity is None:
            prod.quantity = 0
        products[int(pid)] = prod
    for pid, delta in delta_by_pid.items():
        d = int(delta or 0)
        if d == 0:
            continue
        prod = products[int(pid)]
        prod.quantity = int(prod.quantity or 0) + d
        db.add(prod)


def _apply_purchase_item(prod: Product, item: PurchaseItem) -> None:
    """Increment stock and sync discount/trade metadata on a product."""
    if prod.quantity is None:
        prod.quantity = 0
    prod.quantity = int(prod.quantity) + int(item.quantity or 0)
    _sync_purchase_item_pricing(prod, item)


@router.post("/new", response_model=PurchaseOut)
def create_purchase(payload: PurchaseCreate, db: Session = Depends(get_db)):
    now = payload.date or datetime.utcnow().isoformat()
    ensure_not_locked_for_date(db, parse_date_like(now), "Posting purchase")
    supplier_id, supplier_name = _resolve_supplier(db, payload.supplier_id, payload.supplier_name)
    obj = Purchase(
        date=now,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        total=payload.total or 0.0,
        items_json=json.dumps([i.model_dump() for i in payload.items]),
    )
    db.add(obj)
    # Increment stock and update product pricing metadata
    for item in payload.items:
        prod = db.query(Product).filter(Product.id == item.product_id).first()
        if prod:
            _apply_purchase_item(prod, item)
            db.add(prod)
    db.commit()
    db.refresh(obj)
    rebuild_and_persist_cogs_allocations(db)
    return _to_dict(obj)


@router.get("/list", response_model=List[PurchaseOut])
def list_purchases(db: Session = Depends(get_db)):
    items = db.query(Purchase).all()
    return [_to_dict(p) for p in items]


@router.get("/page", response_model=Dict[str, Any])
def list_purchases_page(
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 200))
    q = db.query(Purchase)
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_to_dict(p) for p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": int(math.ceil(total / float(page_size))) if page_size else 1,
    }


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
    ensure_not_locked_for_date(db, parse_date_like(p.date or ""), "Updating purchase")
    ensure_not_locked_for_date(db, parse_date_like(payload.date or p.date or ""), "Updating purchase")
    supplier_id, supplier_name = _resolve_supplier(db, payload.supplier_id, payload.supplier_name)
    # Apply quantity deltas (new - old) so post-sale updates remain consistent.
    try:
        prev_items = json.loads(p.items_json or "[]")
    except Exception:
        prev_items = []
    prev_qty = _aggregate_qty_from_raw_items(prev_items)
    new_qty = _aggregate_qty_from_payload(payload.items)
    all_pids = set(prev_qty.keys()) | set(new_qty.keys())
    delta_by_pid = {
        int(pid): int(new_qty.get(pid, 0) or 0) - int(prev_qty.get(pid, 0) or 0)
        for pid in all_pids
    }
    _apply_quantity_delta(db, delta_by_pid)

    # Sync pricing metadata from new purchase lines.
    for item in payload.items:
        prod = db.query(Product).filter(Product.id == item.product_id).first()
        if prod:
            _sync_purchase_item_pricing(prod, item)
            db.add(prod)

    # Update purchase row
    p.supplier_id = supplier_id
    p.supplier_name = supplier_name
    p.total = payload.total or 0.0
    p.items_json = json.dumps([i.model_dump() for i in payload.items])
    db.add(p)
    db.commit()
    db.refresh(p)
    rebuild_and_persist_cogs_allocations(db)
    return _to_dict(p)


@router.delete("/purchase/{purchase_id}")
def delete_purchase(purchase_id: int, db: Session = Depends(get_db)):
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    ensure_not_locked_for_date(db, parse_date_like(p.date or ""), "Deleting purchase")
    # Revert stock increments; block delete if sold/used stock already consumed it.
    try:
        prev_items = json.loads(p.items_json or "[]")
    except Exception:
        prev_items = []
    prev_qty = _aggregate_qty_from_raw_items(prev_items)
    delta_by_pid = {int(pid): -int(qty or 0) for pid, qty in prev_qty.items()}
    _apply_quantity_delta(db, delta_by_pid)
    db.delete(p)
    db.commit()
    rebuild_and_persist_cogs_allocations(db)
    return {"ok": True}
