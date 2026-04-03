from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from sqlalchemy import func
import json
from datetime import datetime
import math

from ..database import get_db, Base, engine
from ..models import Purchase, Product, Supplier, TransactionCOGSAllocation, PurchasePayment
from ..schemas import (
    PurchaseCreate,
    PurchaseOut,
    PurchaseItem,
    PurchasePaymentOut,
    SupplierPaymentApplyIn,
    SupplierPaymentApplyOut,
    SupplierPaymentAllocationOut,
)
from ..schemas import TransactionPaymentEditIn
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
    total_amount = max(0.0, float(p.total or 0.0))
    paid_amount = max(0.0, float(p.paid or 0.0))
    due_amount = max(0.0, total_amount - paid_amount)
    return PurchaseOut(
        id=p.id,
        date=p.date or "",
        supplier_id=p.supplier_id or 0,
        supplier_name=p.supplier_name or "",
        total=total_amount,
        paid=paid_amount,
        due=due_amount,
        items=items,
        used_in_sales=False,
    )


def _validate_payment_bounds(total: float, paid: float) -> tuple[float, float]:
    """
    Validate that paid does not materially exceed total.

    Uses cent-level rounding and a small tolerance to avoid spurious
    failures caused by floating point rounding (e.g. 199.999999 vs 200.00).
    """
    total_f = max(0.0, float(total or 0.0))
    paid_f = float(paid or 0.0)
    # Normalize to 2 decimal places to match UI amounts.
    total_q = round(total_f + 1e-9, 2)
    paid_q = round(paid_f + 1e-9, 2)
    if paid_q < 0:
        raise HTTPException(status_code=400, detail="Paid amount must be zero or positive")
    # If overpayment is more than 1 cent, block it.
    if paid_q - total_q > 0.01:
        over = paid_q - total_q
        raise HTTPException(
            status_code=400,
            detail=f"Paid amount exceeds purchase total by {over:.2f}. Reduce payment first.",
        )
    # Clamp minor overpayment (<= 1 cent) down to total.
    if paid_q > total_q:
        paid_q = total_q
    return total_q, paid_q


def _payment_to_dict(row: PurchasePayment) -> PurchasePaymentOut:
    return PurchasePaymentOut(
        id=int(row.id or 0),
        purchase_id=int(row.purchase_id or 0),
        supplier_id=int(row.supplier_id or 0),
        date=str(row.date or ""),
        user_id=int(row.user_id or 0),
        amount=float(row.amount or 0.0),
        paid_total=float(row.paid_total or 0.0),
    )


def _record_purchase_payment(
    db: Session,
    purchase_id: int,
    supplier_id: int,
    amount: float,
    paid_total: float,
    user_id: int = 0,
    date: str | None = None,
) -> None:
    if abs(float(amount or 0.0)) < 1e-9:
        return
    db.add(
        PurchasePayment(
            purchase_id=int(purchase_id),
            supplier_id=int(supplier_id or 0),
            date=str(date or datetime.utcnow().isoformat()),
            user_id=int(user_id or 0),
            amount=float(amount or 0.0),
            paid_total=float(paid_total or 0.0),
        )
    )


def _recompute_purchase_payment_totals(db: Session, purchase_id: int) -> float:
    rows = (
        db.query(PurchasePayment)
        .filter(PurchasePayment.purchase_id == int(purchase_id))
        .order_by(PurchasePayment.id.asc())
        .all()
    )
    running = 0.0
    for row in rows:
        running += float(row.amount or 0.0)
        row.paid_total = running
        db.add(row)
    return running


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
    total_amount, paid_amount = _validate_payment_bounds(payload.total or 0.0, payload.paid or 0.0)
    obj = Purchase(
        date=now,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        total=total_amount,
        paid=paid_amount,
        items_json=json.dumps([i.model_dump() for i in payload.items]),
    )
    db.add(obj)
    db.flush()
    # Increment stock and update product pricing metadata
    for item in payload.items:
        prod = db.query(Product).filter(Product.id == item.product_id).first()
        if prod:
            _apply_purchase_item(prod, item)
            db.add(prod)
    _record_purchase_payment(
        db,
        purchase_id=int(obj.id or 0),
        supplier_id=int(supplier_id or 0),
        amount=paid_amount,
        paid_total=paid_amount,
        date=now,
    )
    db.commit()
    db.refresh(obj)
    rebuild_and_persist_cogs_allocations(db)
    # Check whether this purchase is now used in any COGS allocations.
    linked_alloc = (
        db.query(TransactionCOGSAllocation.id)
        .filter(TransactionCOGSAllocation.source_purchase_id == int(obj.id or 0))
        .first()
    )
    out = _to_dict(obj)
    try:
        out.used_in_sales = bool(linked_alloc is not None)
    except Exception:
        pass
    return out


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
    # Block edits once this purchase has contributed to sales profit.
    linked_alloc = (
        db.query(TransactionCOGSAllocation.id)
        .filter(TransactionCOGSAllocation.source_purchase_id == int(purchase_id))
        .first()
    )
    if linked_alloc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot edit this purchase because its cost is already used in sales profit. "
                "Post an adjustment purchase instead."
            ),
        )

    prev_paid = max(0.0, float(p.paid or 0.0))
    requested_total = payload.total if payload.total is not None else float(p.total or 0.0)
    requested_paid = prev_paid if payload.paid is None else float(payload.paid or 0.0)
    total_amount, new_paid = _validate_payment_bounds(requested_total, requested_paid)
    payment_delta = float(new_paid - prev_paid)
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
    p.total = total_amount
    p.paid = new_paid
    p.items_json = json.dumps([i.model_dump() for i in payload.items])
    db.add(p)
    _record_purchase_payment(
        db,
        purchase_id=int(p.id or 0),
        supplier_id=int(supplier_id or 0),
        amount=payment_delta,
        paid_total=new_paid,
        date=str(payload.date or p.date or datetime.utcnow().isoformat()),
    )
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
    linked_alloc = (
        db.query(TransactionCOGSAllocation.id)
        .filter(TransactionCOGSAllocation.source_purchase_id == int(purchase_id))
        .first()
    )
    if linked_alloc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete this purchase because its cost is already used in sales profit. "
                "Edit the purchase instead, or post a reversing adjustment."
            ),
        )
    # Revert stock increments; block delete if sold/used stock already consumed it.
    try:
        prev_items = json.loads(p.items_json or "[]")
    except Exception:
        prev_items = []
    prev_qty = _aggregate_qty_from_raw_items(prev_items)
    delta_by_pid = {int(pid): -int(qty or 0) for pid, qty in prev_qty.items()}
    _apply_quantity_delta(db, delta_by_pid)
    pay_rows = db.query(PurchasePayment).filter(PurchasePayment.purchase_id == int(purchase_id)).all()
    for row in pay_rows:
        db.delete(row)
    db.delete(p)
    db.commit()
    rebuild_and_persist_cogs_allocations(db)
    return {"ok": True}


@router.get("/payments", response_model=List[PurchasePaymentOut])
def list_all_purchase_payments(db: Session = Depends(get_db)):
    rows = db.query(PurchasePayment).order_by(PurchasePayment.id.desc()).all()
    return [_payment_to_dict(r) for r in rows]


@router.get("/purchase/{purchase_id}/payments", response_model=List[PurchasePaymentOut])
def list_purchase_payments(purchase_id: int, db: Session = Depends(get_db)):
    p = db.query(Purchase).filter(Purchase.id == int(purchase_id)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    rows = (
        db.query(PurchasePayment)
        .filter(PurchasePayment.purchase_id == int(purchase_id))
        .order_by(PurchasePayment.id.asc())
        .all()
    )
    return [_payment_to_dict(r) for r in rows]


@router.get("/supplier/{supplier_id}/invoices", response_model=List[PurchaseOut])
def list_supplier_purchases(supplier_id: int, db: Session = Depends(get_db)):
    sid = int(supplier_id or 0)
    if sid <= 0:
        return []
    rows = (
        db.query(Purchase)
        .filter(Purchase.supplier_id == sid)
        .order_by(Purchase.date.desc(), Purchase.id.desc())
        .all()
    )
    return [_to_dict(p) for p in rows]


@router.get("/supplier/{supplier_id}/payments", response_model=List[PurchasePaymentOut])
def list_supplier_payments(supplier_id: int, db: Session = Depends(get_db)):
    sid = int(supplier_id or 0)
    if sid <= 0:
        return []
    rows = (
        db.query(PurchasePayment)
        .filter(PurchasePayment.supplier_id == sid)
        .order_by(PurchasePayment.id.desc())
        .all()
    )
    return [_payment_to_dict(r) for r in rows]


@router.post("/supplier/{supplier_id}/payment", response_model=SupplierPaymentApplyOut)
def apply_supplier_payment(
    supplier_id: int,
    payload: SupplierPaymentApplyIn,
    db: Session = Depends(get_db),
):
    sid = int(supplier_id or 0)
    if sid <= 0:
        raise HTTPException(status_code=400, detail="Invalid supplier ID")
    try:
        amount = float(payload.amount or 0.0)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payment amount")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    rows = (
        db.query(Purchase)
        .filter(Purchase.supplier_id == sid)
        .order_by(Purchase.date.asc(), Purchase.id.asc())
        .all()
    )
    due_rows: list[tuple[Purchase, float, float]] = []
    total_due_before = 0.0
    for p in rows:
        total = max(0.0, float(p.total or 0.0))
        paid = max(0.0, float(p.paid or 0.0))
        due = max(0.0, total - paid)
        if due > 1e-9:
            due_rows.append((p, paid, due))
            total_due_before += due

    if not due_rows:
        raise HTTPException(status_code=400, detail="No due purchase invoices found for this supplier")
    # Compare in cents to avoid float rounding issues across many invoices.
    amount_q = round(float(amount or 0.0) + 1e-9, 2)
    total_due_q = round(float(total_due_before or 0.0) + 1e-9, 2)
    if amount_q - total_due_q > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds merged due by {amount_q - total_due_q:.2f}",
        )

    payment_date = str(payload.date or "").strip() or datetime.utcnow().isoformat()
    ensure_not_locked_for_date(db, parse_date_like(payment_date), "Applying supplier payment")
    # Never apply more than the merged due, even if the caller sent a slightly
    # higher amount (within tolerance); the extra is simply ignored.
    remaining = min(amount_q, total_due_q)
    allocations: list[SupplierPaymentAllocationOut] = []
    for p, paid_before, due_before in due_rows:
        if remaining <= 1e-9:
            break
        applied = min(due_before, remaining)
        if applied <= 1e-9:
            continue
        paid_after = paid_before + applied
        p.paid = paid_after
        db.add(p)
        _record_purchase_payment(
            db,
            purchase_id=int(p.id or 0),
            supplier_id=sid,
            amount=applied,
            paid_total=paid_after,
            user_id=int(payload.user_id or 0),
            date=payment_date,
        )
        allocations.append(
            SupplierPaymentAllocationOut(
                purchase_id=int(p.id or 0),
                amount_applied=float(applied),
                paid_before=float(paid_before),
                paid_after=float(paid_after),
                due_before=float(due_before),
                due_after=float(max(0.0, due_before - applied)),
            )
        )
        remaining -= applied

    if not allocations:
        raise HTTPException(status_code=400, detail="Could not allocate payment to due purchase invoices")

    db.commit()
    total_applied = float(amount - max(0.0, remaining))
    total_due_after = max(0.0, total_due_before - total_applied)
    return SupplierPaymentApplyOut(
        supplier_id=sid,
        total_due_before=float(total_due_before),
        total_applied=float(total_applied),
        total_due_after=float(total_due_after),
        allocations=allocations,
    )


@router.put("/purchase/{purchase_id}/payment/{payment_id}", response_model=PurchaseOut)
def update_purchase_payment(
    purchase_id: int,
    payment_id: int,
    payload: TransactionPaymentEditIn,
    db: Session = Depends(get_db),
):
    p = db.query(Purchase).filter(Purchase.id == int(purchase_id)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    row = (
        db.query(PurchasePayment)
        .filter(PurchasePayment.id == int(payment_id), PurchasePayment.purchase_id == int(purchase_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Payment entry not found")
    ensure_not_locked_for_date(db, parse_date_like(row.date or ""), "Editing purchase payment")
    try:
        new_amount = float(payload.amount or 0.0)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid amount")
    if new_amount < 0:
        raise HTTPException(status_code=400, detail="Amount must be zero or positive")

    rows = db.query(PurchasePayment).filter(PurchasePayment.purchase_id == int(purchase_id)).all()
    running_total = 0.0
    for r in rows:
        running_total += float(r.amount or 0.0)
    prev_amount = float(row.amount or 0.0)
    candidate_paid = running_total - prev_amount + new_amount
    _validate_payment_bounds(float(p.total or 0.0), candidate_paid)

    row.amount = new_amount
    db.add(row)
    new_paid = _recompute_purchase_payment_totals(db, int(purchase_id))
    p.paid = max(0.0, float(new_paid or 0.0))
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_dict(p)


@router.delete("/purchase/{purchase_id}/payment/{payment_id}", response_model=PurchaseOut)
def delete_purchase_payment(
    purchase_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
):
    p = db.query(Purchase).filter(Purchase.id == int(purchase_id)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    row = (
        db.query(PurchasePayment)
        .filter(PurchasePayment.id == int(payment_id), PurchasePayment.purchase_id == int(purchase_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Payment entry not found")
    ensure_not_locked_for_date(db, parse_date_like(row.date or ""), "Deleting purchase payment")
    (
        db.query(PurchasePayment)
        .filter(PurchasePayment.id == int(payment_id), PurchasePayment.purchase_id == int(purchase_id))
        .delete(synchronize_session=False)
    )
    new_paid = _recompute_purchase_payment_totals(db, int(purchase_id))
    p.paid = max(0.0, float(new_paid or 0.0))
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_dict(p)


@router.delete("/payment/{payment_id}", response_model=PurchaseOut)
def delete_purchase_payment_by_id(
    payment_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a purchase payment using only its payment ID.

    Mirrors delete_purchase_payment but does not require the caller to
    know the purchase_id; it is resolved from the payment row.
    """
    row = db.query(PurchasePayment).filter(PurchasePayment.id == int(payment_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase payment not found")
    purchase_id = int(row.purchase_id or 0)
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found for payment")
    ensure_not_locked_for_date(db, parse_date_like(row.date or ""), "Deleting purchase payment")
    db.query(PurchasePayment).filter(PurchasePayment.id == int(payment_id)).delete(synchronize_session=False)
    new_paid = _recompute_purchase_payment_totals(db, purchase_id)
    p.paid = max(0.0, float(new_paid or 0.0))
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_dict(p)
