import os
from fastapi import FastAPI
from sqlalchemy import inspect, text
from .database import Base, engine, SessionLocal
from .routers import users, products
from .routers import customers, settings
from .routers import companies, suppliers, purchases, transactions, reports
from .routers import held_sales
from .services.cogs import rebuild_and_persist_cogs_allocations


def create_app() -> FastAPI:
    # Ensure app metadata exists
    os.environ.setdefault("APPNAME", "pharmaspot")
    app = FastAPI(title="PharmaSpot API")
    Base.metadata.create_all(bind=engine)
    _ensure_schema_updates()
    _bootstrap_cogs_allocations()

    app.include_router(users.router)
    app.include_router(products.router)
    app.include_router(customers.router)
    app.include_router(settings.router)
    app.include_router(companies.router)
    app.include_router(suppliers.router)
    app.include_router(purchases.router)
    app.include_router(transactions.router)
    app.include_router(held_sales.router)
    app.include_router(reports.router)

    return app


def _ensure_schema_updates() -> None:
    # Lightweight runtime schema patch for existing DBs.
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "products" in tables:
            product_cols = {c.get("name") for c in insp.get_columns("products")}
            if "is_active" not in product_cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE products ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                except Exception:
                    pass
            if "purchase_price" in product_cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE products DROP COLUMN purchase_price"))
                except Exception:
                    # Some DBs or versions may not support DROP COLUMN; keep startup resilient.
                    pass
        # Remove deprecated transaction profit column when present.
        if "transactions" in tables:
            tx_cols = {c.get("name") for c in insp.get_columns("transactions")}
            if "profit" in tx_cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE transactions DROP COLUMN profit"))
                except Exception:
                    # Some DBs or versions may not support DROP COLUMN; keep startup resilient.
                    pass
        if "purchases" in tables:
            purchase_cols = {c.get("name") for c in insp.get_columns("purchases")}
            if "paid" not in purchase_cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE purchases ADD COLUMN paid FLOAT DEFAULT 0"))
                except Exception:
                    pass
        if "users" in tables:
            user_cols = {c.get("name") for c in insp.get_columns("users")}
            for col in ("perm_see_cost", "perm_give_discount", "perm_edit_invoice", "perm_delete_payment"):
                if col not in user_cols:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT 0"))
                    except Exception:
                        pass
    except Exception:
        # Keep startup resilient if DB user lacks ALTER permission.
        pass


def _bootstrap_cogs_allocations() -> None:
    # Keep persisted COGS allocations in sync on startup for existing datasets.
    db = SessionLocal()
    try:
        rebuild_and_persist_cogs_allocations(db)
    except Exception:
        # Startup should remain resilient if bootstrap fails.
        pass
    finally:
        db.close()


app = create_app()
