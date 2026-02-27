from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
try:
    from sqlalchemy.dialects.mysql import LONGTEXT as MYSQL_LONGTEXT  # type: ignore
except Exception:  # pragma: no cover - dialect not present
    MYSQL_LONGTEXT = None  # type: ignore
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(191), unique=True, index=True, nullable=False)
    fullname = Column(String(255), default="")
    password_hash = Column(String(255), nullable=False)
    status = Column(String(64), default="")

    perm_products = Column(Boolean, default=False)
    perm_transactions = Column(Boolean, default=False)
    perm_users = Column(Boolean, default=False)
    perm_settings = Column(Boolean, default=False)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    expirationDate = Column(String(32), default="")
    price = Column(Float, default=0.0)
    company_id = Column(Integer, ForeignKey("companies.id"), default=0)
    quantity = Column(Integer, default=0)
    name = Column(String(255), nullable=False)
    img = Column(String(255), default="")
    # New canonical purchase fields
    discount_pct = Column(Float, default=0.0)   # last purchase discount percent
    trade_price = Column(Float, default=0.0)    # last purchase trade price (unit)
    created_at = Column(DateTime, server_default=func.now())


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(64), default="")
    email = Column(String(255), default="")
    address = Column(String(255), default="")
    is_active = Column(Boolean, default=True)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(191), primary_key=True, index=True)
    value = Column(String(1024), default="")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(191), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(32), default="")
    supplier_id = Column(Integer, default=0)
    supplier_name = Column(String(255), default="")
    total = Column(Float, default=0.0)
    # Use LONGTEXT on MySQL to accommodate large payloads; Text elsewhere
    items_json = Column(MYSQL_LONGTEXT if MYSQL_LONGTEXT is not None else Text, default="[]")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(32), default="")
    user_id = Column(Integer, default=0)
    customer_id = Column(Integer, default=0)
    till = Column(Integer, default=0)
    status = Column(Integer, default=1)
    total = Column(Float, default=0.0)
    paid = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    # Match purchases: allow large payloads on MySQL
    items_json = Column(MYSQL_LONGTEXT if MYSQL_LONGTEXT is not None else Text, default="[]")
    inventory_deducted = Column(Boolean, default=False)


class TransactionPayment(Base):
    __tablename__ = "transaction_payments"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, index=True, nullable=False)
    date = Column(String(32), default="")
    user_id = Column(Integer, default=0)
    amount = Column(Float, default=0.0)
    paid_total = Column(Float, default=0.0)


# Track per-purchase discount and trade price entries per product
"""
Note: Columns minStock, purchase_discount, and sale_discount were removed
in favor of discount_pct and trade_price on products.
Run the alter script in python_backend/tools to migrate an existing DB.
"""
