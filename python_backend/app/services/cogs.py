from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime, date
from typing import Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import (
    Purchase,
    Transaction,
    TransactionCOGSAllocation,
    Product,
    Company,
)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except Exception:
        return int(default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def _parse_dt(raw_value: str) -> Optional[datetime]:
    txt = str(raw_value or "").strip()
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except Exception:
        pass
    try:
        normalized = txt.replace("T", " ")
        return datetime.strptime(normalized.split(".", 1)[0], "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    try:
        return datetime.strptime(txt, "%Y-%m-%d")
    except Exception:
        return None


def _parse_date(raw_value: str) -> Optional[date]:
    dt = _parse_dt(raw_value)
    return dt.date() if dt else None


def _sale_unit_price(item: dict) -> float:
    unit = item.get("unit_price")
    if unit is not None:
        return max(0.0, _to_float(unit, 0.0))
    trade = item.get("trade_price")
    if trade is not None:
        extra_pct = max(0.0, _to_float(item.get("extra_discount_pct", 0.0), 0.0))
        return max(0.0, _to_float(trade, 0.0) * (1.0 - (extra_pct / 100.0)))
    retail = _to_float(item.get("retail_price", 0.0), 0.0)
    disc_pct = max(0.0, _to_float(item.get("discount_pct", 0.0), 0.0))
    extra_pct = max(0.0, _to_float(item.get("extra_discount_pct", 0.0), 0.0))
    trade_calc = retail * (1.0 - (disc_pct / 100.0))
    return max(0.0, trade_calc * (1.0 - (extra_pct / 100.0)))


def _purchase_unit_cost(item: dict) -> float:
    price = item.get("price")
    if price is not None:
        return max(0.0, _to_float(price, 0.0))
    trade = item.get("trade_price")
    if trade is not None:
        return max(0.0, _to_float(trade, 0.0))
    retail = _to_float(item.get("retail_price", 0.0), 0.0)
    disc_pct = max(0.0, _to_float(item.get("discount_pct", 0.0), 0.0))
    extra_pct = max(0.0, _to_float(item.get("extra_discount_pct", 0.0), 0.0))
    trade_calc = retail * (1.0 - (disc_pct / 100.0))
    return max(0.0, trade_calc * (1.0 - (extra_pct / 100.0)))


def _product_cost_hint(prod: Product) -> float:
    # Prefer explicit purchase-like unit cost snapshots first.
    for key in ("trade_price",):
        val = _to_float(getattr(prod, key, 0.0), 0.0)
        if val > 1e-9:
            return float(val)
    # Fallback: infer from retail + discount metadata.
    retail = _to_float(getattr(prod, "price", 0.0), 0.0)
    disc = _to_float(getattr(prod, "discount_pct", 0.0), 0.0)
    if retail > 1e-9:
        return max(0.0, retail * (1.0 - (max(0.0, disc) / 100.0)))
    return 0.0


def _parse_json_array(raw_json: str) -> list[dict]:
    try:
        arr = json.loads(raw_json or "[]")
    except Exception:
        arr = []
    out = []
    for it in arr or []:
        if isinstance(it, dict):
            out.append(it)
    return out


def _build_allocation_rows(
    purchases: list[Purchase],
    transactions: list[Transaction],
    products: list[Product] | None = None,
) -> list[dict]:
    product_cost_hint_by_id: dict[int, float] = {}
    for p in products or []:
        pid = _to_int(getattr(p, "id", 0), 0)
        if pid <= 0:
            continue
        hint = max(0.0, _to_float(_product_cost_hint(p), 0.0))
        if hint > 1e-9:
            product_cost_hint_by_id[pid] = float(hint)

    events: list[tuple] = []

    for p in purchases or []:
        p_dt = _parse_dt(p.date or "")
        sort_dt = p_dt if p_dt is not None else datetime.min
        items = _parse_json_array(p.items_json or "[]")
        for idx, it in enumerate(items):
            pid = _to_int(it.get("product_id", 0), 0)
            qty = max(0, _to_int(it.get("quantity", 0), 0))
            if pid <= 0 or qty <= 0:
                continue
            unit_cost = _purchase_unit_cost(it)
            events.append(
                (
                    sort_dt,
                    0,  # purchase before sale at same timestamp
                    _to_int(p.id, 0),
                    int(idx),
                    {
                        "type": "purchase",
                        "purchase_id": _to_int(p.id, 0),
                        "supplier_id": _to_int(getattr(p, "supplier_id", 0), 0),
                        "product_id": int(pid),
                        "quantity": int(qty),
                        "unit_cost": float(unit_cost),
                    },
                )
            )

    for t in transactions or []:
        tx_dt = _parse_dt(t.date or "")
        sort_dt = tx_dt if tx_dt is not None else datetime.min
        tx_date_txt = str(t.date or "")
        discount_pct = max(0.0, _to_float(getattr(t, "discount", 0.0), 0.0))
        discount_factor = max(0.0, 1.0 - (discount_pct / 100.0))
        items = _parse_json_array(t.items_json or "[]")
        for idx, it in enumerate(items):
            pid = _to_int(it.get("id", 0), 0)
            qty = max(0, _to_int(it.get("quantity", 0), 0))
            if pid <= 0 or qty <= 0:
                continue
            unit_sale = _sale_unit_price(it) * discount_factor
            fallback_unit_cost = max(0.0, _to_float(product_cost_hint_by_id.get(int(pid), 0.0), 0.0))
            events.append(
                (
                    sort_dt,
                    1,
                    _to_int(t.id, 0),
                    int(idx),
                    {
                        "type": "sale",
                        "transaction_id": _to_int(t.id, 0),
                        "transaction_item_index": int(idx),
                        "transaction_date": tx_date_txt,
                        "user_id": _to_int(getattr(t, "user_id", 0), 0),
                        "product_id": int(pid),
                        "quantity": int(qty),
                        "unit_sale": float(unit_sale),
                        "fallback_unit_cost": float(fallback_unit_cost),
                    },
                )
            )

    events.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    available_lots: dict[int, deque] = defaultdict(deque)
    pending_negative: dict[int, deque] = defaultdict(deque)
    last_known_cost: dict[int, float] = {}
    out_rows: list[dict] = []

    for _sort_dt, _priority, _owner, _idx, ev in events:
        etype = str(ev.get("type", ""))
        pid = _to_int(ev.get("product_id", 0), 0)
        qty = max(0.0, _to_float(ev.get("quantity", 0), 0.0))
        if pid <= 0 or qty <= 1e-9:
            continue

        if etype == "purchase":
            purchase_id = _to_int(ev.get("purchase_id", 0), 0)
            supplier_id = _to_int(ev.get("supplier_id", 0), 0)
            unit_cost = max(0.0, _to_float(ev.get("unit_cost", 0.0), 0.0))
            if unit_cost <= 1e-9:
                unit_cost = max(0.0, _to_float(last_known_cost.get(pid, 0.0), 0.0))
            last_known_cost[pid] = unit_cost

            remaining = qty
            pendq = pending_negative[pid]
            while remaining > 1e-9 and pendq:
                pend = pendq[0]
                take = min(remaining, max(0.0, _to_float(pend.get("qty_remaining", 0.0), 0.0)))
                if take <= 1e-9:
                    pendq.popleft()
                    continue
                sale_unit = max(0.0, _to_float(pend.get("unit_sale", 0.0), 0.0))
                sale_amount = float(take) * sale_unit
                cost_amount = float(take) * unit_cost
                out_rows.append(
                    {
                        "transaction_id": _to_int(pend.get("transaction_id", 0), 0),
                        "transaction_item_index": _to_int(pend.get("transaction_item_index", 0), 0),
                        "transaction_date": str(pend.get("transaction_date", "") or ""),
                        "user_id": _to_int(pend.get("user_id", 0), 0),
                        "product_id": int(pid),
                        "quantity": float(take),
                        "unit_sale": float(sale_unit),
                        "unit_cost": float(unit_cost),
                        "sale_amount": float(sale_amount),
                        "cost_amount": float(cost_amount),
                        "profit_amount": float(sale_amount - cost_amount),
                        "source_purchase_id": int(purchase_id),
                        "source_supplier_id": int(supplier_id),
                        "provisional": False,
                        "settled": True,
                    }
                )
                pend["qty_remaining"] = max(0.0, _to_float(pend.get("qty_remaining", 0.0), 0.0) - float(take))
                remaining -= float(take)
                if _to_float(pend.get("qty_remaining", 0.0), 0.0) <= 1e-9:
                    pendq.popleft()

            if remaining > 1e-9:
                available_lots[pid].append(
                    {
                        "qty_remaining": float(remaining),
                        "unit_cost": float(unit_cost),
                        "purchase_id": int(purchase_id),
                        "supplier_id": int(supplier_id),
                    }
                )
            continue

        if etype == "sale":
            tx_id = _to_int(ev.get("transaction_id", 0), 0)
            tx_item_idx = _to_int(ev.get("transaction_item_index", 0), 0)
            tx_date_txt = str(ev.get("transaction_date", "") or "")
            tx_user_id = _to_int(ev.get("user_id", 0), 0)
            unit_sale = max(0.0, _to_float(ev.get("unit_sale", 0.0), 0.0))
            fallback_unit_cost = max(0.0, _to_float(ev.get("fallback_unit_cost", 0.0), 0.0))
            remaining = float(qty)
            lots = available_lots[pid]
            while remaining > 1e-9 and lots:
                lot = lots[0]
                lot_qty = max(0.0, _to_float(lot.get("qty_remaining", 0.0), 0.0))
                if lot_qty <= 1e-9:
                    lots.popleft()
                    continue
                take = min(remaining, lot_qty)
                unit_cost = max(0.0, _to_float(lot.get("unit_cost", 0.0), 0.0))
                sale_amount = float(take) * unit_sale
                cost_amount = float(take) * unit_cost
                out_rows.append(
                    {
                        "transaction_id": int(tx_id),
                        "transaction_item_index": int(tx_item_idx),
                        "transaction_date": tx_date_txt,
                        "user_id": int(tx_user_id),
                        "product_id": int(pid),
                        "quantity": float(take),
                        "unit_sale": float(unit_sale),
                        "unit_cost": float(unit_cost),
                        "sale_amount": float(sale_amount),
                        "cost_amount": float(cost_amount),
                        "profit_amount": float(sale_amount - cost_amount),
                        "source_purchase_id": _to_int(lot.get("purchase_id", 0), 0),
                        "source_supplier_id": _to_int(lot.get("supplier_id", 0), 0),
                        "provisional": False,
                        "settled": True,
                    }
                )
                lot["qty_remaining"] = lot_qty - float(take)
                remaining -= float(take)
                if _to_float(lot.get("qty_remaining", 0.0), 0.0) <= 1e-9:
                    lots.popleft()

            if remaining > 1e-9:
                provisional_unit = max(0.0, _to_float(last_known_cost.get(pid, 0.0), 0.0))
                if provisional_unit <= 1e-9:
                    provisional_unit = fallback_unit_cost
                pending_negative[pid].append(
                    {
                        "transaction_id": int(tx_id),
                        "transaction_item_index": int(tx_item_idx),
                        "transaction_date": tx_date_txt,
                        "user_id": int(tx_user_id),
                        "unit_sale": float(unit_sale),
                        "qty_remaining": float(remaining),
                        "provisional_unit_cost": float(provisional_unit),
                    }
                )

    for pid, pendq in pending_negative.items():
        while pendq:
            pend = pendq.popleft()
            qty_remaining = max(0.0, _to_float(pend.get("qty_remaining", 0.0), 0.0))
            if qty_remaining <= 1e-9:
                continue
            unit_sale = max(0.0, _to_float(pend.get("unit_sale", 0.0), 0.0))
            unit_cost = max(0.0, _to_float(pend.get("provisional_unit_cost", 0.0), 0.0))
            sale_amount = float(qty_remaining) * unit_sale
            cost_amount = float(qty_remaining) * unit_cost
            out_rows.append(
                {
                    "transaction_id": _to_int(pend.get("transaction_id", 0), 0),
                    "transaction_item_index": _to_int(pend.get("transaction_item_index", 0), 0),
                    "transaction_date": str(pend.get("transaction_date", "") or ""),
                    "user_id": _to_int(pend.get("user_id", 0), 0),
                    "product_id": int(pid),
                    "quantity": float(qty_remaining),
                    "unit_sale": float(unit_sale),
                    "unit_cost": float(unit_cost),
                    "sale_amount": float(sale_amount),
                    "cost_amount": float(cost_amount),
                    "profit_amount": float(sale_amount - cost_amount),
                    "source_purchase_id": 0,
                    "source_supplier_id": 0,
                    "provisional": True,
                    "settled": False,
                }
            )

    return out_rows


def rebuild_and_persist_cogs_allocations(db: Session) -> dict[str, int]:
    purchases = list(db.query(Purchase).all())
    transactions = list(db.query(Transaction).all())
    products = list(db.query(Product).all())
    rows = _build_allocation_rows(purchases, transactions, products=products)
    db.query(TransactionCOGSAllocation).delete(synchronize_session=False)
    for r in rows:
        db.add(TransactionCOGSAllocation(**r))
    db.commit()
    return {"allocations": len(rows), "transactions": len(transactions), "purchases": len(purchases)}


def build_profit_reconciliation(
    db: Session,
    start_date: str = "",
    end_date: str = "",
    user_id: int = 0,
) -> dict:
    uid = max(0, _to_int(user_id, 0))
    start_d = _parse_date(start_date)
    end_d = _parse_date(end_date)

    products = db.query(Product).all()
    product_name_by_id = {int(p.id): str(p.name or "") for p in products}

    purchases = db.query(Purchase).all()
    purchase_events: list[dict] = []
    for p in purchases:
        d = _parse_date(p.date or "")
        items = _parse_json_array(p.items_json or "[]")
        for it in items:
            pid = _to_int(it.get("product_id", 0), 0)
            qty = max(0.0, _to_float(it.get("quantity", 0), 0.0))
            if pid <= 0 or qty <= 1e-9:
                continue
            unit_cost = _purchase_unit_cost(it)
            purchase_events.append(
                {
                    "date": d,
                    "product_id": int(pid),
                    "qty": float(qty),
                    "value": float(qty) * float(unit_cost),
                }
            )

    q = db.query(TransactionCOGSAllocation)
    if uid > 0:
        q = q.filter(TransactionCOGSAllocation.user_id == uid)
    alloc_rows = q.all()
    cogs_events: list[dict] = []
    for a in alloc_rows:
        d = _parse_date(a.transaction_date or "")
        cogs_events.append(
            {
                "date": d,
                "product_id": _to_int(a.product_id, 0),
                "qty": max(0.0, _to_float(a.quantity, 0.0)),
                "cogs": max(0.0, _to_float(a.cost_amount, 0.0)),
                "sales": max(0.0, _to_float(a.sale_amount, 0.0)),
                "provisional": bool(a.provisional),
            }
        )

    all_dates = [e["date"] for e in purchase_events if e.get("date") is not None] + [
        e["date"] for e in cogs_events if e.get("date") is not None
    ]
    if start_d is None and all_dates:
        start_d = min(all_dates)
    if end_d is None and all_dates:
        end_d = max(all_dates)
    if start_d is None:
        start_d = date.today()
    if end_d is None:
        end_d = date.today()

    def _is_before(d: Optional[date]) -> bool:
        return d is not None and d < start_d

    def _is_period(d: Optional[date]) -> bool:
        return d is not None and start_d <= d <= end_d

    def _to_end(d: Optional[date]) -> bool:
        return d is not None and d <= end_d

    rec: dict[int, dict] = defaultdict(
        lambda: {
            "opening_qty": 0.0,
            "opening_value": 0.0,
            "purchases_qty": 0.0,
            "purchases_value": 0.0,
            "closing_qty": 0.0,
            "closing_value": 0.0,
            "expected_cogs": 0.0,
            "actual_cogs": 0.0,
            "difference": 0.0,
            "sales_value": 0.0,
            "profit": 0.0,
            "provisional_open_cost": 0.0,
        }
    )

    purchase_qty_before: dict[int, float] = defaultdict(float)
    purchase_val_before: dict[int, float] = defaultdict(float)
    purchase_qty_period: dict[int, float] = defaultdict(float)
    purchase_val_period: dict[int, float] = defaultdict(float)
    purchase_qty_to_end: dict[int, float] = defaultdict(float)
    purchase_val_to_end: dict[int, float] = defaultdict(float)

    sale_qty_before: dict[int, float] = defaultdict(float)
    cogs_before: dict[int, float] = defaultdict(float)
    sale_qty_period: dict[int, float] = defaultdict(float)
    cogs_period: dict[int, float] = defaultdict(float)
    sales_period: dict[int, float] = defaultdict(float)
    sale_qty_to_end: dict[int, float] = defaultdict(float)
    cogs_to_end: dict[int, float] = defaultdict(float)
    provisional_open_to_end: dict[int, float] = defaultdict(float)

    for e in purchase_events:
        pid = _to_int(e.get("product_id", 0), 0)
        d = e.get("date")
        qty = max(0.0, _to_float(e.get("qty", 0.0), 0.0))
        val = max(0.0, _to_float(e.get("value", 0.0), 0.0))
        if pid <= 0:
            continue
        if _is_before(d):
            purchase_qty_before[pid] += qty
            purchase_val_before[pid] += val
        if _is_period(d):
            purchase_qty_period[pid] += qty
            purchase_val_period[pid] += val
        if _to_end(d):
            purchase_qty_to_end[pid] += qty
            purchase_val_to_end[pid] += val

    for e in cogs_events:
        pid = _to_int(e.get("product_id", 0), 0)
        d = e.get("date")
        qty = max(0.0, _to_float(e.get("qty", 0.0), 0.0))
        cogs_val = max(0.0, _to_float(e.get("cogs", 0.0), 0.0))
        sale_val = max(0.0, _to_float(e.get("sales", 0.0), 0.0))
        if pid <= 0:
            continue
        if _is_before(d):
            sale_qty_before[pid] += qty
            cogs_before[pid] += cogs_val
        if _is_period(d):
            sale_qty_period[pid] += qty
            cogs_period[pid] += cogs_val
            sales_period[pid] += sale_val
        if _to_end(d):
            sale_qty_to_end[pid] += qty
            cogs_to_end[pid] += cogs_val
            if bool(e.get("provisional", False)):
                provisional_open_to_end[pid] += cogs_val

    pids = set(purchase_qty_before.keys()) | set(purchase_qty_period.keys()) | set(purchase_qty_to_end.keys())
    pids |= set(sale_qty_before.keys()) | set(sale_qty_period.keys()) | set(sale_qty_to_end.keys())

    items: list[dict] = []
    for pid in sorted(pids):
        opening_qty = purchase_qty_before[pid] - sale_qty_before[pid]
        opening_val = purchase_val_before[pid] - cogs_before[pid]
        purchases_qty = purchase_qty_period[pid]
        purchases_val = purchase_val_period[pid]
        closing_qty = purchase_qty_to_end[pid] - sale_qty_to_end[pid]
        closing_val = purchase_val_to_end[pid] - cogs_to_end[pid]
        expected_cogs = opening_val + purchases_val - closing_val
        actual_cogs = cogs_period[pid]
        diff = expected_cogs - actual_cogs
        sales_val = sales_period[pid]
        profit_val = sales_val - actual_cogs
        provisional_open_cost = provisional_open_to_end[pid]

        # Skip pure zeros to keep reconciliation readable.
        if (
            abs(opening_val) < 1e-9
            and abs(purchases_val) < 1e-9
            and abs(closing_val) < 1e-9
            and abs(actual_cogs) < 1e-9
            and abs(sales_val) < 1e-9
            and abs(provisional_open_cost) < 1e-9
        ):
            continue

        mismatch = abs(diff) > 0.05
        items.append(
            {
                "product_id": int(pid),
                "product_name": product_name_by_id.get(int(pid), f"ID {int(pid)}"),
                "opening_qty": float(opening_qty),
                "opening_value": float(opening_val),
                "purchases_qty": float(purchases_qty),
                "purchases_value": float(purchases_val),
                "closing_qty": float(closing_qty),
                "closing_value": float(closing_val),
                "expected_cogs": float(expected_cogs),
                "actual_cogs": float(actual_cogs),
                "difference": float(diff),
                "sales_value": float(sales_val),
                "profit": float(profit_val),
                "provisional_open_cost": float(provisional_open_cost),
                "mismatch": bool(mismatch),
            }
        )

    summary = {
        "opening_value": float(sum(float(i.get("opening_value", 0.0) or 0.0) for i in items)),
        "purchases_value": float(sum(float(i.get("purchases_value", 0.0) or 0.0) for i in items)),
        "closing_value": float(sum(float(i.get("closing_value", 0.0) or 0.0) for i in items)),
        "expected_cogs": float(sum(float(i.get("expected_cogs", 0.0) or 0.0) for i in items)),
        "actual_cogs": float(sum(float(i.get("actual_cogs", 0.0) or 0.0) for i in items)),
        "sales_value": float(sum(float(i.get("sales_value", 0.0) or 0.0) for i in items)),
        "profit": float(sum(float(i.get("profit", 0.0) or 0.0) for i in items)),
        "provisional_open_cost": float(sum(float(i.get("provisional_open_cost", 0.0) or 0.0) for i in items)),
        "mismatch_count": int(sum(1 for i in items if bool(i.get("mismatch", False)))),
    }
    summary["difference"] = float(summary["expected_cogs"] - summary["actual_cogs"])

    return {
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "user_id": int(uid),
        "summary": summary,
        "items": items,
    }


def estimate_product_fifo_cost(
    db: Session,
    product_id: int,
    quantity: float,
) -> dict:
    """Estimate cost for the *next* sale quantity of a product using FIFO lots.

    The algorithm:
    - Reads all purchases for the product and computes purchased_qty and value per purchase.
    - Reads TransactionCOGSAllocation to see how much of each purchase has already been consumed.
    - Builds remaining lots per purchase and applies FIFO across purchases to cover the requested
      sale quantity. Any oversell tail falls back to the product-level cost hint.
    """
    pid = _to_int(product_id, 0)
    qty = max(0.0, _to_float(quantity, 0.0))
    if pid <= 0 or qty <= 1e-9:
        return {
            "product_id": int(pid),
            "quantity": float(qty),
            "unit_cost": 0.0,
            "cost_total": 0.0,
        }

    # Aggregate purchased quantity and value per purchase for this product.
    purchases = db.query(Purchase).all()
    lots_raw: list[dict] = []
    for p in purchases:
        d = _parse_date(p.date or "")
        items = _parse_json_array(p.items_json or "[]")
        total_qty = 0.0
        total_val = 0.0
        for it in items:
            if _to_int(it.get("product_id", 0), 0) != pid:
                continue
            item_qty = max(0.0, _to_float(it.get("quantity", 0), 0.0))
            if item_qty <= 1e-9:
                continue
            unit_cost = _purchase_unit_cost(it)
            total_qty += item_qty
            total_val += item_qty * unit_cost
        if total_qty <= 1e-9:
            continue
        lots_raw.append(
            {
                "purchase_id": _to_int(getattr(p, "id", 0), 0),
                "supplier_id": _to_int(getattr(p, "supplier_id", 0), 0),
                "date": d,
                "purchased_qty": float(total_qty),
                "purchased_value": float(total_val),
            }
        )

    def _fallback_hint() -> float:
        prod = db.query(Product).filter(Product.id == pid).first()
        if not prod:
            return 0.0
        return max(0.0, _to_float(_product_cost_hint(prod), 0.0))

    if not lots_raw:
        unit_cost = _fallback_hint()
        return {
            "product_id": int(pid),
            "quantity": float(qty),
            "unit_cost": float(unit_cost),
            "cost_total": float(unit_cost * qty),
        }

    # How much of each purchase has already been consumed in COGS?
    alloc_rows = (
        db.query(
            TransactionCOGSAllocation.source_purchase_id,
            func.sum(TransactionCOGSAllocation.quantity),
        )
        .filter(
            TransactionCOGSAllocation.product_id == pid,
            TransactionCOGSAllocation.source_purchase_id != 0,
        )
        .group_by(TransactionCOGSAllocation.source_purchase_id)
        .all()
    )
    allocated_by_purchase: dict[int, float] = {}
    for pur_id, used_qty in alloc_rows:
        allocated_by_purchase[_to_int(pur_id, 0)] = max(0.0, _to_float(used_qty, 0.0))

    # Build remaining lots per purchase.
    avail_lots: list[dict] = []
    for lot in lots_raw:
        pur_id = _to_int(lot.get("purchase_id", 0), 0)
        purchased_qty = max(0.0, _to_float(lot.get("purchased_qty", 0.0), 0.0))
        if pur_id <= 0 or purchased_qty <= 1e-9:
            continue
        allocated = max(0.0, _to_float(allocated_by_purchase.get(pur_id, 0.0), 0.0))
        remaining = max(0.0, purchased_qty - allocated)
        if remaining <= 1e-9:
            continue
        value = max(0.0, _to_float(lot.get("purchased_value", 0.0), 0.0))
        unit_cost = max(0.0, value / purchased_qty) if purchased_qty > 1e-9 else 0.0
        avail_lots.append(
            {
                "purchase_id": pur_id,
                "supplier_id": _to_int(lot.get("supplier_id", 0), 0),
                "date": lot.get("date"),
                "remaining_qty": float(remaining),
                "unit_cost": float(unit_cost),
            }
        )

    if not avail_lots:
        # All purchased stock has been consumed, but we still want a stable
        # cost hint. Use the weighted-average cost of all historical purchases
        # for this product before falling back to the product-level hint.
        total_purchased_qty = sum(max(0.0, _to_float(l.get("purchased_qty", 0.0), 0.0)) for l in lots_raw)
        total_purchased_val = sum(max(0.0, _to_float(l.get("purchased_value", 0.0), 0.0)) for l in lots_raw)
        unit_cost = 0.0
        if total_purchased_qty > 1e-9 and total_purchased_val >= 0.0:
            unit_cost = max(0.0, total_purchased_val / total_purchased_qty)
        if unit_cost <= 1e-9:
            unit_cost = _fallback_hint()
        return {
            "product_id": int(pid),
            "quantity": float(qty),
            "unit_cost": float(unit_cost),
            "cost_total": float(unit_cost * qty),
        }

    # FIFO across remaining lots.
    avail_lots.sort(key=lambda lot: ((lot.get("date") or date.min), lot.get("purchase_id", 0)))
    remaining_sale = qty
    total_cost = 0.0
    for lot in avail_lots:
        if remaining_sale <= 1e-9:
            break
        lot_rem = max(0.0, _to_float(lot.get("remaining_qty", 0.0), 0.0))
        if lot_rem <= 1e-9:
            continue
        take = min(remaining_sale, lot_rem)
        if take <= 1e-9:
            continue
        unit_cost = max(0.0, _to_float(lot.get("unit_cost", 0.0), 0.0))
        total_cost += take * unit_cost
        remaining_sale -= take

    if remaining_sale > 1e-9:
        # Oversell tail: use product-level hint so we don't crash.
        tail_unit = _fallback_hint()
        total_cost += remaining_sale * tail_unit

    unit_cost_overall = 0.0
    if qty > 1e-9:
        unit_cost_overall = max(0.0, total_cost / qty)

    return {
        "product_id": int(pid),
        "quantity": float(qty),
        "unit_cost": float(unit_cost_overall),
        "cost_total": float(total_cost),
    }


def build_product_purchase_lots(
    db: Session,
    product_id: int,
) -> dict:
    """Return per-purchase remaining quantity lots for a product.

    Each lot contains:
    - purchase_id
    - supplier_id
    - date (ISO date string from purchase row)
    - purchased_qty
    - allocated_qty
    - remaining_qty
    - unit_cost (average unit cost within the purchase for that product)
    """
    pid = _to_int(product_id, 0)
    if pid <= 0:
        return {"product_id": int(pid), "lots": []}

    purchases = db.query(Purchase).all()
    lots_raw: list[dict] = []
    for p in purchases:
        raw_date = str(getattr(p, "date", "") or "")
        items = _parse_json_array(p.items_json or "[]")
        total_qty = 0.0
        total_val = 0.0
        for it in items:
            if _to_int(it.get("product_id", 0), 0) != pid:
                continue
            item_qty = max(0.0, _to_float(it.get("quantity", 0), 0.0))
            if item_qty <= 1e-9:
                continue
            unit_cost = _purchase_unit_cost(it)
            total_qty += item_qty
            total_val += item_qty * unit_cost
        if total_qty <= 1e-9:
            continue
        lots_raw.append(
            {
                "purchase_id": _to_int(getattr(p, "id", 0), 0),
                "supplier_id": _to_int(getattr(p, "supplier_id", 0), 0),
                "date_str": raw_date,
                "purchased_qty": float(total_qty),
                "purchased_value": float(total_val),
            }
        )

    if not lots_raw:
        return {"product_id": int(pid), "lots": []}

    alloc_rows = (
        db.query(
            TransactionCOGSAllocation.source_purchase_id,
            func.sum(TransactionCOGSAllocation.quantity),
        )
        .filter(
            TransactionCOGSAllocation.product_id == pid,
            TransactionCOGSAllocation.source_purchase_id != 0,
        )
        .group_by(TransactionCOGSAllocation.source_purchase_id)
        .all()
    )
    allocated_by_purchase: dict[int, float] = {}
    for pur_id, used_qty in alloc_rows:
        allocated_by_purchase[_to_int(pur_id, 0)] = max(0.0, _to_float(used_qty, 0.0))

    lots: list[dict] = []
    for lot in lots_raw:
        pur_id = _to_int(lot.get("purchase_id", 0), 0)
        purchased_qty = max(0.0, _to_float(lot.get("purchased_qty", 0.0), 0.0))
        if pur_id <= 0 or purchased_qty <= 1e-9:
            continue
        allocated = max(0.0, _to_float(allocated_by_purchase.get(pur_id, 0.0), 0.0))
        remaining = max(0.0, purchased_qty - allocated)
        value = max(0.0, _to_float(lot.get("purchased_value", 0.0), 0.0))
        unit_cost = max(0.0, value / purchased_qty) if purchased_qty > 1e-9 else 0.0
        lots.append(
            {
                "purchase_id": pur_id,
                "supplier_id": _to_int(lot.get("supplier_id", 0), 0),
                "date": str(lot.get("date_str") or ""),
                "purchased_qty": float(purchased_qty),
                "allocated_qty": float(allocated),
                "remaining_qty": float(remaining),
                "unit_cost": float(unit_cost),
            }
        )

    lots.sort(key=lambda row: (_parse_date(row.get("date", "")) or date.min, row.get("purchase_id", 0)))
    return {"product_id": int(pid), "lots": lots}


def allocate_cogs_for_transaction(db: Session, transaction_id: int) -> None:
    """
    Incrementally (re)allocate COGS rows for a single transaction.

    Instead of rebuilding allocations for all invoices, this function:
    - Removes existing TransactionCOGSAllocation rows for the given
      transaction_id.
    - Looks at current purchase lots minus allocations from *other*
      transactions.
    - Allocates this transaction's items on top of the remaining lots
      using FIFO.

    This preserves which purchases older invoices used when you delete
    or edit another invoice.
    """
    tx_id = _to_int(transaction_id, 0)
    if tx_id <= 0:
        return

    t = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not t:
        return

    # Remove previous allocations for this transaction so they no longer
    # count against remaining purchase quantities.
    db.query(TransactionCOGSAllocation).filter(
        TransactionCOGSAllocation.transaction_id == tx_id
    ).delete(synchronize_session=False)

    items = _parse_json_array(t.items_json or "[]")
    if not items:
        db.commit()
        return

    discount_pct = max(0.0, _to_float(getattr(t, "discount", 0.0), 0.0))
    discount_factor = max(0.0, 1.0 - (discount_pct / 100.0))
    tx_date_txt = str(t.date or "")
    tx_user_id = _to_int(getattr(t, "user_id", 0), 0)

    # Cache lots per product so multiple lines for the same product share
    # a single remaining-quantity view.
    lots_cache: dict[int, list[dict]] = {}

    for item_index, it in enumerate(items):
        pid = _to_int(it.get("id", 0), 0)
        qty = max(0.0, _to_float(it.get("quantity", 0), 0.0))
        if pid <= 0 or qty <= 1e-9:
            continue

        # Load remaining lots for this product using current allocations
        # from *other* transactions.
        if pid not in lots_cache:
            lots_info = build_product_purchase_lots(db, product_id=pid) or {}
            lots = list(lots_info.get("lots") or [])
            lots.sort(
                key=lambda lot: (
                    _parse_date(lot.get("date", "")) or date.min,
                    lot.get("purchase_id", 0),
                )
            )
            lots_cache[pid] = lots
        lots = lots_cache[pid]

        unit_sale_base = _sale_unit_price(it)
        unit_sale = max(0.0, unit_sale_base * discount_factor)

        remaining = qty
        # Allocate from concrete purchase lots first.
        for lot in lots:
            if remaining <= 1e-9:
                break
            lot_rem = max(0.0, _to_float(lot.get("remaining_qty", 0.0), 0.0))
            if lot_rem <= 1e-9:
                continue
            take = min(remaining, lot_rem)
            if take <= 1e-9:
                continue
            unit_cost = max(0.0, _to_float(lot.get("unit_cost", 0.0), 0.0))
            sale_amount = float(take) * unit_sale
            cost_amount = float(take) * unit_cost
            db.add(
                TransactionCOGSAllocation(
                    transaction_id=int(tx_id),
                    transaction_item_index=int(item_index),
                    transaction_date=tx_date_txt,
                    user_id=int(tx_user_id),
                    product_id=int(pid),
                    quantity=float(take),
                    unit_sale=float(unit_sale),
                    unit_cost=float(unit_cost),
                    sale_amount=float(sale_amount),
                    cost_amount=float(cost_amount),
                    profit_amount=float(sale_amount - cost_amount),
                    source_purchase_id=int(lot.get("purchase_id", 0) or 0),
                    source_supplier_id=int(lot.get("supplier_id", 0) or 0),
                    provisional=False,
                    settled=True,
                )
            )
            lot["remaining_qty"] = float(lot_rem - take)
            remaining -= float(take)

        if remaining > 1e-9:
            # Oversell tail: use a stable product-level cost hint and
            # mark as provisional (no specific purchase).
            prod = db.query(Product).filter(Product.id == pid).first()
            hint_unit = 0.0
            if prod:
                hint_unit = max(0.0, _to_float(_product_cost_hint(prod), 0.0))
            unit_cost = hint_unit
            sale_amount = float(remaining) * unit_sale
            cost_amount = float(remaining) * unit_cost
            db.add(
                TransactionCOGSAllocation(
                    transaction_id=int(tx_id),
                    transaction_item_index=int(item_index),
                    transaction_date=tx_date_txt,
                    user_id=int(tx_user_id),
                    product_id=int(pid),
                    quantity=float(remaining),
                    unit_sale=float(unit_sale),
                    unit_cost=float(unit_cost),
                    sale_amount=float(sale_amount),
                    cost_amount=float(cost_amount),
                    profit_amount=float(sale_amount - cost_amount),
                    source_purchase_id=0,
                    source_supplier_id=0,
                    provisional=True,
                    settled=True,
                )
            )

    db.commit()


def build_company_inventory_snapshot(
    db: Session,
    include_inactive: bool = False,
    q: str = "",
) -> dict:
    query = db.query(Company)
    if not include_inactive:
        query = query.filter(Company.is_active == True)  # noqa: E712
    needle = str(q or "").strip().lower()
    if needle:
        query = query.filter(func.lower(Company.name).like(f"%{needle}%"))
    companies = list(query.all())

    company_ids = [int(c.id or 0) for c in companies if int(c.id or 0) > 0]
    if not company_ids:
        return {
            "items": [],
            "summary": {
                "total_companies": 0,
                "total_products": 0,
                "total_quantity": 0.0,
                "total_value": 0.0,
            },
        }

    prod_q = db.query(Product).filter(Product.company_id.in_(company_ids))
    if not include_inactive:
        prod_q = prod_q.filter(Product.is_active == True)  # noqa: E712
    products = list(prod_q.all())

    # Use reconciliation closing valuation when available (captures mixed purchase costs),
    # otherwise fallback to product-level cost hint.
    rec = build_profit_reconciliation(db, start_date="", end_date="", user_id=0)
    closing_by_pid: dict[int, tuple[float, float]] = {}
    for row in list(rec.get("items") or []):
        pid = _to_int(row.get("product_id", 0), 0)
        if pid <= 0:
            continue
        cqty = max(0.0, _to_float(row.get("closing_qty", 0.0), 0.0))
        cval = max(0.0, _to_float(row.get("closing_value", 0.0), 0.0))
        closing_by_pid[pid] = (cqty, cval)

    agg: dict[int, dict] = defaultdict(
        lambda: {
            "company_id": 0,
            "company_name": "",
            "product_count": 0,
            "quantity": 0.0,
            "inventory_value": 0.0,
        }
    )
    company_name_by_id = {int(c.id or 0): str(c.name or "") for c in companies}

    for p in products:
        pid = _to_int(getattr(p, "id", 0), 0)
        cid = _to_int(getattr(p, "company_id", 0), 0)
        if pid <= 0 or cid <= 0:
            continue
        qty = max(0.0, _to_float(getattr(p, "quantity", 0), 0.0))
        cost_hint = max(0.0, _to_float(_product_cost_hint(p), 0.0))
        closing_qty, closing_val = closing_by_pid.get(pid, (0.0, 0.0))
        avg_cost = 0.0
        if closing_qty > 1e-9 and closing_val >= 0.0:
            avg_cost = max(0.0, closing_val / closing_qty)
        if avg_cost <= 1e-9:
            avg_cost = cost_hint
        inv_val = max(0.0, qty * avg_cost)

        slot = agg[cid]
        slot["company_id"] = int(cid)
        slot["company_name"] = company_name_by_id.get(int(cid), f"ID {int(cid)}")
        slot["product_count"] = int(slot["product_count"]) + 1
        slot["quantity"] = float(slot["quantity"]) + float(qty)
        slot["inventory_value"] = float(slot["inventory_value"]) + float(inv_val)

    items: list[dict] = []
    for c in companies:
        cid = _to_int(getattr(c, "id", 0), 0)
        slot = dict(agg.get(cid) or {})
        items.append(
            {
                "company_id": int(cid),
                "company_name": str(getattr(c, "name", "") or ""),
                "product_count": int(slot.get("product_count", 0) or 0),
                "quantity": float(slot.get("quantity", 0.0) or 0.0),
                "inventory_value": float(slot.get("inventory_value", 0.0) or 0.0),
            }
        )

    items.sort(key=lambda x: (-float(x.get("inventory_value", 0.0) or 0.0), str(x.get("company_name", "")).lower()))
    summary = {
        "total_companies": int(len(items)),
        "total_products": int(sum(int(i.get("product_count", 0) or 0) for i in items)),
        "total_quantity": float(sum(float(i.get("quantity", 0.0) or 0.0) for i in items)),
        "total_value": float(sum(float(i.get("inventory_value", 0.0) or 0.0) for i in items)),
    }
    return {"items": items, "summary": summary}
