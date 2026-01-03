import os
from fastapi import FastAPI
from .database import Base, engine
from .routers import users, products
from .routers import customers, settings
from .routers import companies, purchases, transactions


def create_app() -> FastAPI:
    # Ensure app metadata exists
    os.environ.setdefault("APPNAME", "pharmaspot")
    app = FastAPI(title="PharmaSpot API")
    Base.metadata.create_all(bind=engine)

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


app = create_app()
