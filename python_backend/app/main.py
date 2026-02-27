import os
from fastapi import FastAPI
from sqlalchemy import inspect, text
from .database import Base, engine
from .routers import users, products
from .routers import customers, settings
from .routers import companies, purchases, transactions


def create_app() -> FastAPI:
    # Ensure app metadata exists
    os.environ.setdefault("APPNAME", "pharmaspot")
    app = FastAPI(title="PharmaSpot API")
    Base.metadata.create_all(bind=engine)
    _ensure_schema_updates()

    app.include_router(users.router)
    app.include_router(products.router)
    app.include_router(customers.router)
    app.include_router(settings.router)
    app.include_router(companies.router)
    app.include_router(purchases.router)
    app.include_router(transactions.router)

    @app.get("/")
    def root():
        return {"message": "POS Server Online."}

    return app


def _ensure_schema_updates() -> None:
    # Lightweight runtime schema patch for existing DBs.
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "products" in tables:
            product_cols = {c.get("name") for c in insp.get_columns("products")}
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
    except Exception:
        # Keep startup resilient if DB user lacks ALTER permission.
        pass


app = create_app()
