"""
Create a single purchase to account for Hamdard products whose current stock
exceeds what has been recorded via purchases.

Logic:
- Load all products for company named "Hamdard" (case-insensitive).
- Sum quantities for those product IDs across all purchase items.
- If current product.quantity > summed purchase quantity, the difference is
  added as a single new purchase ("Adjustment: Hamdard") with today's date.
- Retail/trade/discount values are taken from the current product fields.

Run:
    python python_backend/tools/create_hamdard_adjustment_purchase.py
"""

import json
from datetime import datetime
from pathlib import Path
import sys

# Ensure python_backend on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # type: ignore
from app.models import Product, Purchase, Company  # type: ignore


def main():
    db = SessionLocal()
    try:
        company = (
            db.query(Company)
            .filter(Company.name.ilike("hamdard"))
            .first()
        )
        if not company:
            print("No company named 'Hamdard' found.")
            return

        hamdard_products = db.query(Product).filter(Product.company_id == company.id).all()
        if not hamdard_products:
            print("No products for Hamdard found.")
            return

        # Sum purchased qty per product
        purchased_qty: dict[int, int] = {}
        for p in db.query(Purchase).all():
            try:
                items = json.loads(p.items_json or "[]")
            except Exception:
                items = []
            for it in items:
                try:
                    pid = int(it.get("product_id", 0) or 0)
                    qty = int(it.get("quantity", 0) or 0)
                    purchased_qty[pid] = purchased_qty.get(pid, 0) + qty
                except Exception:
                    pass

        items_to_add = []
        for prod in hamdard_products:
            current_qty = int(prod.quantity or 0)
            recorded = purchased_qty.get(prod.id, 0)
            diff = current_qty - recorded
            if diff > 0:
                items_to_add.append(
                    {
                        "product_id": prod.id,
                        "company_id": prod.company_id,
                        "quantity": diff,
                        "price": float(prod.trade_price or prod.price or 0.0),
                        "retail_price": float(prod.price or 0.0),
                        "discount_pct": float(getattr(prod, "discount_pct", 0.0) or 0.0),
                        "extra_discount_pct": 0.0,
                        "trade_price": float(prod.trade_price or prod.price or 0.0),
                    }
                )

        if not items_to_add:
            print("No adjustment needed; all Hamdard products accounted for.")
            return

        total = sum(i["price"] * i["quantity"] for i in items_to_add)
        purchase = Purchase(
            date=datetime.utcnow().isoformat(),
            supplier_id=0,
            supplier_name="Adjustment: Hamdard",
            total=total,
            items_json=json.dumps(items_to_add),
        )
        db.add(purchase)
        db.commit()
        print(f"Adjustment purchase created with {len(items_to_add)} items, total={total:.2f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
