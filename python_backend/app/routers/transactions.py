from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime

from ..database import get_db, Base, engine
from ..models import Transaction, Product, TransactionPayment
from ..schemas import (
    TransactionCreate,
    TransactionOut,
    TransactionItem,
    TransactionPaymentOut,
    TransactionPaymentEditIn,
)


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/", response_model=str)
def index():
    return "Transactions API"


def _as_optional_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_items_json(items_json: str) -> list[TransactionItem]:
    items: list[TransactionItem] = []
    try:
        raw = json.loads(items_json or "[]")
    except Exception:
        raw = []
    for it in raw:
        try:
            pid = int(it.get("id"))
            qty = max(0, int(it.get("quantity", 0) or 0))
        except Exception:
            continue
        if pid > 0 and qty > 0:
            items.append(
                TransactionItem(
                    id=pid,
                    quantity=qty,
                    name=str(it.get("name")) if it.get("name") is not None else None,
                    retail_price=_as_optional_float(it.get("retail_price")),
                    discount_pct=_as_optional_float(it.get("discount_pct")),
                    extra_discount_pct=_as_optional_float(it.get("extra_discount_pct")),
                    trade_price=_as_optional_float(it.get("trade_price")),
                    unit_price=_as_optional_float(it.get("unit_price")),
                )
            )
    return items


def _normalize_items(items: list[TransactionItem]) -> list[TransactionItem]:
    out: list[TransactionItem] = []
    for it in items or []:
        try:
            pid = int(it.id)
            qty = max(0, int(it.quantity or 0))
        except Exception:
            continue
        if pid > 0 and qty > 0:
            out.append(
                TransactionItem(
                    id=pid,
                    quantity=qty,
                    name=getattr(it, "name", None),
                    retail_price=_as_optional_float(getattr(it, "retail_price", None)),
                    discount_pct=_as_optional_float(getattr(it, "discount_pct", None)),
                    extra_discount_pct=_as_optional_float(getattr(it, "extra_discount_pct", None)),
                    trade_price=_as_optional_float(getattr(it, "trade_price", None)),
                    unit_price=_as_optional_float(getattr(it, "unit_price", None)),
                )
            )
    return out


def _items_json(items: list[TransactionItem]) -> str:
    payload = []
    for i in items or []:
        payload.append(
            {
                "id": int(i.id),
                "quantity": int(i.quantity),
                "name": getattr(i, "name", None),
                "retail_price": _as_optional_float(getattr(i, "retail_price", None)),
                "discount_pct": _as_optional_float(getattr(i, "discount_pct", None)),
                "extra_discount_pct": _as_optional_float(getattr(i, "extra_discount_pct", None)),
                "trade_price": _as_optional_float(getattr(i, "trade_price", None)),
                "unit_price": _as_optional_float(getattr(i, "unit_price", None)),
            }
        )
    return json.dumps(payload)


def _apply_inventory(items: list[TransactionItem], db: Session, add_back: bool) -> None:
    for it in items:
        prod = db.query(Product).filter(Product.id == int(it.id)).first()
        if not prod:
            continue
        if prod.quantity is None:
            prod.quantity = 0
        qty = max(0, int(it.quantity or 0))
        if add_back:
            prod.quantity = int(prod.quantity) + qty
        else:
            prod.quantity = int(prod.quantity) - qty
        db.add(prod)


def _validate_payment_bounds(total: float, paid: float) -> tuple[float, float]:
    total_f = max(0.0, float(total or 0.0))
    paid_f = float(paid or 0.0)
    if paid_f < 0:
        raise HTTPException(status_code=400, detail="Paid amount must be zero or positive")
    if paid_f - total_f > 1e-6:
        over = paid_f - total_f
        raise HTTPException(
            status_code=400,
            detail=f"Paid amount exceeds invoice total by {over:.2f}. Reduce payment first.",
        )
    return total_f, paid_f


def _payment_to_dict(p: TransactionPayment) -> TransactionPaymentOut:
    return TransactionPaymentOut(
        id=int(p.id or 0),
        transaction_id=int(p.transaction_id or 0),
        date=p.date or "",
        user_id=int(p.user_id or 0),
        amount=float(p.amount or 0.0),
        paid_total=float(p.paid_total or 0.0),
    )


def _record_payment(
    db: Session,
    transaction_id: int,
    amount: float,
    paid_total: float,
    user_id: int = 0,
    date: str | None = None,
) -> None:
    if abs(float(amount or 0.0)) < 1e-9:
        return
    db.add(
        TransactionPayment(
            transaction_id=int(transaction_id),
            date=str(date or datetime.utcnow().isoformat()),
            user_id=int(user_id or 0),
            amount=float(amount or 0.0),
            paid_total=float(paid_total or 0.0),
        )
    )


def _recompute_payment_totals(db: Session, transaction_id: int) -> float:
    rows = (
        db.query(TransactionPayment)
        .filter(TransactionPayment.transaction_id == transaction_id)
        .order_by(TransactionPayment.id.asc())
        .all()
    )
    running = 0.0
    for row in rows:
        running += float(row.amount or 0.0)
        row.paid_total = running
        db.add(row)
    return running


def _to_dict(t: Transaction) -> TransactionOut:
    items = _parse_items_json(t.items_json or "[]")
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


def _enrich_item_snapshots(items: list[TransactionItem], db: Session) -> list[TransactionItem]:
    out: list[TransactionItem] = []
    for it in items or []:
        pid = int(it.id or 0)
        qty = max(0, int(it.quantity or 0))
        if pid <= 0 or qty <= 0:
            continue
        prod = db.query(Product).filter(Product.id == pid).first()

        name = getattr(it, "name", None)
        if not name and prod:
            name = str(getattr(prod, "name", "") or "")

        retail = _as_optional_float(getattr(it, "retail_price", None))
        if retail is None and prod:
            retail = _as_optional_float(getattr(prod, "price", None))
        if retail is None:
            retail = 0.0

        discount_pct = _as_optional_float(getattr(it, "discount_pct", None))
        if discount_pct is None and prod:
            discount_pct = _as_optional_float(getattr(prod, "discount_pct", None))
        if discount_pct is None:
            discount_pct = 0.0

        extra_pct = _as_optional_float(getattr(it, "extra_discount_pct", None))
        if extra_pct is None:
            extra_pct = 0.0

        trade_price = _as_optional_float(getattr(it, "trade_price", None))
        if trade_price is None:
            trade_price = float(retail) * (1.0 - (float(discount_pct) / 100.0))

        unit_price = _as_optional_float(getattr(it, "unit_price", None))
        if unit_price is None:
            unit_price = float(trade_price or 0.0) * (1.0 - (float(extra_pct) / 100.0))

        out.append(
            TransactionItem(
                id=pid,
                quantity=qty,
                name=name,
                retail_price=retail,
                discount_pct=discount_pct,
                extra_discount_pct=extra_pct,
                trade_price=trade_price,
                unit_price=unit_price,
            )
        )
    return out


def _has_full_item_snapshot(items: list[TransactionItem]) -> bool:
    required = ("retail_price", "discount_pct", "extra_discount_pct", "trade_price", "unit_price")
    for it in items or []:
        for key in required:
            if getattr(it, key, None) is None:
                return False
    return True


@router.post("/new", response_model=TransactionOut)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    now = payload.date or datetime.utcnow().isoformat()
    norm_items = _enrich_item_snapshots(_normalize_items(payload.items), db)
    total_amount, paid_amount = _validate_payment_bounds(payload.total or 0.0, payload.paid or 0.0)
    obj = Transaction(
        date=now,
        user_id=payload.user_id or 0,
        customer_id=payload.customer_id or 0,
        till=payload.till or 0,
        status=payload.status or 1,
        total=total_amount,
        paid=paid_amount,
        discount=payload.discount or 0.0,
        items_json=_items_json(norm_items),
    )
    db.add(obj)
    db.flush()
    # Always deduct inventory at checkout, even for partial payments.
    if not obj.inventory_deducted:
        _apply_inventory(norm_items, db, add_back=False)
        obj.inventory_deducted = True
    _record_payment(
        db,
        transaction_id=int(obj.id or 0),
        amount=paid_amount,
        paid_total=paid_amount,
        user_id=int(payload.user_id or 0),
        date=now,
    )
    db.commit()
    db.refresh(obj)
    return _to_dict(obj)


@router.get("/list", response_model=List[TransactionOut])
def list_transactions(db: Session = Depends(get_db)):
    rows = db.query(Transaction).order_by(Transaction.id.desc()).all()
    return [_to_dict(t) for t in rows]


@router.get("/transaction/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Auto-backfill legacy invoices that lack snapshot fields.
    parsed = _parse_items_json(t.items_json or "[]")
    if parsed and not _has_full_item_snapshot(parsed):
        snap_items = _enrich_item_snapshots(parsed, db)
        t.items_json = _items_json(snap_items)
        db.add(t)
        db.commit()
        db.refresh(t)
    return _to_dict(t)


@router.get("/transaction/{transaction_id}/payments", response_model=List[TransactionPaymentOut])
def list_transaction_payments(transaction_id: int, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    rows = (
        db.query(TransactionPayment)
        .filter(TransactionPayment.transaction_id == transaction_id)
        .order_by(TransactionPayment.id.asc())
        .all()
    )
    return [_payment_to_dict(p) for p in rows]


@router.put("/transaction/{transaction_id}/payment/{payment_id}", response_model=TransactionOut)
def update_transaction_payment(
    transaction_id: int,
    payment_id: int,
    payload: TransactionPaymentEditIn,
    db: Session = Depends(get_db),
):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    row = (
        db.query(TransactionPayment)
        .filter(TransactionPayment.id == payment_id, TransactionPayment.transaction_id == transaction_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Payment entry not found")
    try:
        new_amount = float(payload.amount or 0.0)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid amount")
    if new_amount < 0:
        raise HTTPException(status_code=400, detail="Amount must be zero or positive")
    rows = (
        db.query(TransactionPayment)
        .filter(TransactionPayment.transaction_id == transaction_id)
        .all()
    )
    running_total = 0.0
    for p in rows:
        running_total += float(p.amount or 0.0)
    prev_amount = float(row.amount or 0.0)
    candidate_paid = running_total - prev_amount + new_amount
    _validate_payment_bounds(t.total or 0.0, candidate_paid)
    row.amount = new_amount
    db.add(row)
    new_paid = _recompute_payment_totals(db, transaction_id)
    t.paid = max(0.0, float(new_paid or 0.0))
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


@router.put("/transaction/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, payload: TransactionCreate, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    prev_paid = float(t.paid or 0.0)
    total_amount, new_paid = _validate_payment_bounds(payload.total or 0.0, payload.paid or 0.0)
    payment_delta = new_paid - prev_paid
    norm_items = _enrich_item_snapshots(_normalize_items(payload.items), db)
    prev_items = _parse_items_json(t.items_json or "[]")
    was_deducted = bool(t.inventory_deducted)
    # Keep inventory balanced when editing an existing invoice.
    if was_deducted:
        _apply_inventory(prev_items, db, add_back=True)
    _apply_inventory(norm_items, db, add_back=False)
    t.inventory_deducted = True
    # Update values
    t.user_id = payload.user_id or 0
    t.customer_id = payload.customer_id or 0
    t.till = payload.till or 0
    t.status = payload.status or 1
    t.total = total_amount
    t.paid = new_paid
    t.discount = payload.discount or 0.0
    t.items_json = _items_json(norm_items)
    _record_payment(
        db,
        transaction_id=transaction_id,
        amount=payment_delta,
        paid_total=new_paid,
        user_id=int(payload.user_id or t.user_id or 0),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


@router.delete("/transaction/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # If inventory was deducted, add stock back before deletion
    if t.inventory_deducted:
        try:
            items = json.loads(t.items_json or "[]")
        except Exception:
            items = []
        for it in items:
            try:
                pid = int(it.get("id"))
                qty = int(it.get("quantity", 0))
                prod = db.query(Product).filter(Product.id == pid).first()
                if prod and prod.quantity is not None:
                    prod.quantity = int(prod.quantity) + qty
                    db.add(prod)
            except Exception:
                pass
    rows = db.query(TransactionPayment).filter(TransactionPayment.transaction_id == transaction_id).all()
    for p in rows:
        db.delete(p)
    db.delete(t)
    db.commit()
    return {"ok": True}
