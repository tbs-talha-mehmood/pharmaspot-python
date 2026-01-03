import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Iterable
import math

# Support running as a module (python -m python_backend.tools.migrate)
# and as a script (python python_backend/tools/migrate.py)
try:
    from app.database import Base, engine, SessionLocal  # type: ignore
    from app.models import (
        Product,
        Customer,
        Setting,
        Company,
        Purchase,
        Transaction,
    )  # type: ignore
except ModuleNotFoundError:
    try:
        from python_backend.app.database import Base, engine, SessionLocal  # type: ignore
        from python_backend.app.models import (
            Product,
            Customer,
            Setting,
            Company,
            Purchase,
            Transaction,
        )  # type: ignore
    except ModuleNotFoundError:
        import sys
        from pathlib import Path as _Path

        # Add project python_backend root to sys.path then retry
        sys.path.append(str(_Path(__file__).resolve().parents[1]))
        from app.database import Base, engine, SessionLocal  # type: ignore
        from app.models import (
            Product,
            Customer,
            Setting,
            Company,
            Purchase,
            Transaction,
        )  # type: ignore


def default_appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    appname = os.environ.get("APPNAME") or "pharmaspot"
    return Path(base) / appname / "server" / "databases"


def iter_nedb(filepath: Path) -> Iterable[Dict[str, Any]]:
    """Yield the latest document state for each _id from a NeDB datafile.
    Very lightweight parser: reads line-delimited JSON and keeps last occurrence per _id.
    """
    latest: Dict[str, Dict[str, Any]] = {}
    if not filepath.exists():
        return latest.values()
    try:
        with filepath.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                _id = obj.get("_id")
                if _id is None:
                    continue
                # Skip tombstones if present
                if obj.get("$$deleted") or obj.get("_deleted"):
                    latest.pop(_id, None)
                    continue
                latest[_id] = obj
    except Exception:
        pass
    return latest.values()


def to_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default


def to_float(val, default=0.0):
    try:
        f = float(val)
        # MySQL does not accept NaN or Infinity values
        if not math.isfinite(f) or f != f:  # f!=f catches NaN
            return default
        return f
    except Exception:
        return default


def migrate_nedb_to_sqlite(src_dir: Path):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Customers
        for cu in iter_nedb(src_dir / "customers.db"):
            obj = Customer(
                name=cu.get("name") or cu.get("fullname") or cu.get("customer") or "",
                phone=str(cu.get("phone", "")),
                email=str(cu.get("email", "")),
                address=str(cu.get("address", "")),
            )
            try:
                cid = to_int(cu.get("_id"))
                if cid:
                    obj.id = cid
            except Exception:
                pass
            if obj.name:
                db.merge(obj)

        # Products
        product_src = src_dir / "products.db"
        if not product_src.exists():
            product_src = src_dir / "inventory.db"
        for p in iter_nedb(product_src):
            obj = Product(
                name=p.get("name", ""),
                barcode=to_int(p.get("barcode"), None),
                price=to_float(p.get("price", 0.0)),
                category=str(p.get("category", "")),
                quantity=to_int(p.get("quantity", 0)),
                expirationDate=str(p.get("expirationDate", "")),
                stock=to_int(p.get("stock", 1)),
                minStock=to_int(p.get("minStock", 0)),
                img=str(p.get("image") or p.get("img") or ""),
                purchase_discount=to_float(p.get("purchase_discount", 0.0)),
                sale_discount=to_float(p.get("sale_discount", 0.0)),
            )
            try:
                pid = to_int(p.get("_id"))
                if pid:
                    obj.id = pid
            except Exception:
                pass
            db.merge(obj)

        # Settings
        for sdoc in iter_nedb(src_dir / "settings.db"):
            # Flatten doc to key/value pairs
            for k, v in sdoc.items():
                if k.startswith("_"):
                    continue
                db.merge(Setting(key=str(k), value=str(v)))

        # Purchases
        for pd in iter_nedb(src_dir / "purchases.db"):
            items = pd.get("items") or []
            # Update costs on products
            for it in items:
                try:
                    prod = db.query(Product).filter(Product.id == to_int(it.get("product_id"))).first()
                    if prod:
                        prod.cost = to_float(it.get("price", 0.0))
                        prod.quantity = to_int(prod.quantity or 0) + to_int(it.get("quantity", 0))
                        db.add(prod)
                except Exception:
                    pass
            pobj = Purchase(
                id=to_int(pd.get("_id"), None) or None,
                date=str(pd.get("date", "")),
                supplier_id=to_int(pd.get("supplier_id", 0)),
                supplier_name=str(pd.get("supplier_name", "")),
                total=to_float(pd.get("total", 0.0)),
                items_json=json.dumps(items),
            )
            if pobj.id:
                db.merge(pobj)
            else:
                db.add(pobj)

        # Transactions
        for td in iter_nedb(src_dir / "transactions.db"):
            items = td.get("items") or []
            tobj = Transaction(
                id=to_int(td.get("_id"), None) or None,
                date=str(td.get("date", "")),
                user_id=to_int(td.get("user_id", 0)),
                customer_id=to_int(td.get("customer_id", 0)),
                till=to_int(td.get("till", 0)),
                status=to_int(td.get("status", 1)),
                total=to_float(td.get("total", 0.0)),
                paid=to_float(td.get("paid", 0.0)),
                discount=to_float(td.get("discount", 0.0)),
                items_json=json.dumps([{ "id": to_int(i.get("id")), "quantity": to_int(i.get("quantity", 0)) } for i in items]),
                inventory_deducted=bool(td.get("inventory_deducted", False)),
                profit=to_float(td.get("profit", 0.0)),
            )
            if tobj.id:
                db.merge(tobj)
            else:
                db.add(tobj)

        db.commit()
    finally:
        db.close()


def clone_sqlite(src_db: Path, dst_db: Path):
    # Simple file copy when cloning entire DB
    if not src_db.exists():
        raise SystemExit(f"Source DB not found: {src_db}")
    dst_db.parent.mkdir(parents=True, exist_ok=True)
    data = src_db.read_bytes()
    dst_db.write_bytes(data)
    print(f"Cloned {src_db} -> {dst_db}")


def main():
    parser = argparse.ArgumentParser(description="Migrate data to new database")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("nedb-to-sqlite", help="Import NeDB files into current DB (engine from env)")
    p1.add_argument("--src", type=str, default=str(default_appdata_dir()), help="Path to NeDB directory")

    p2 = sub.add_parser("clone-sqlite", help="Clone existing SQLite DB to a new file")
    p2.add_argument("--src", type=str, help="Source SQLite path (app.db)")
    p2.add_argument("--dst", type=str, help="Destination SQLite path")

    args = parser.parse_args()
    if args.cmd == "nedb-to-sqlite":
        migrate_nedb_to_sqlite(Path(args.src))
        print("NeDB -> SQLite migration complete")
    elif args.cmd == "clone-sqlite":
        if not args.src or not args.dst:
            raise SystemExit("--src and --dst are required for clone-sqlite")
        clone_sqlite(Path(args.src), Path(args.dst))


if __name__ == "__main__":
    main()
