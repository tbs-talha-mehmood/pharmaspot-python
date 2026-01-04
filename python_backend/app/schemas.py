from typing import Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    fullname: Optional[str] = ""
    password: str
    perm_products: Optional[bool] = False
    perm_transactions: Optional[bool] = False
    perm_users: Optional[bool] = False
    perm_settings: Optional[bool] = False


class UserOut(BaseModel):
    id: int
    username: str
    fullname: str
    status: str
    perm_products: bool
    perm_transactions: bool
    perm_users: bool
    perm_settings: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    auth: bool
    id: Optional[int] = None
    username: Optional[str] = None
    fullname: Optional[str] = None
    status: Optional[str] = None
    perm_products: Optional[bool] = None
    perm_transactions: Optional[bool] = None
    perm_users: Optional[bool] = None
    perm_settings: Optional[bool] = None
    message: Optional[str] = None


class ProductCreate(BaseModel):
    id: Optional[int] = None
    barcode: Optional[int] = None
    expirationDate: Optional[str] = ""
    price: Optional[float] = 0.0
    company_id: Optional[int] = 0
    quantity: Optional[int] = None
    name: str
    minStock: Optional[int] = 0
    img: Optional[str] = ""
    # New canonical purchase metadata (kept optional for backward compatibility)
    discount_pct: Optional[float] = None
    trade_price: Optional[float] = None
    purchase_discount: Optional[float] = 0.0
    sale_discount: Optional[float] = 0.0


class ProductOut(BaseModel):
    id: int
    barcode: Optional[int]
    expirationDate: str
    price: float
    company_id: int
    company_name: str
    quantity: int
    name: str
    minStock: int
    img: str
    discount_pct: float
    trade_price: float
    purchase_discount: float
    sale_discount: float

    class Config:
        from_attributes = True


# Customers
class CustomerCreate(BaseModel):
    id: Optional[int] = None
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    address: str
    is_active: bool

    class Config:
        from_attributes = True


# Settings
class SettingIn(BaseModel):
    key: str
    value: str


class SettingOut(BaseModel):
    key: str
    value: str

    class Config:
        from_attributes = True


# Companies, Purchases, Transactions
class CompanyCreate(BaseModel):
    id: Optional[int] = None
    name: str


class CompanyOut(BaseModel):
    id: int
    name: str
    is_active: bool

    class Config:
        from_attributes = True


class PurchaseItem(BaseModel):
    product_id: int
    company_id: Optional[int] = None
    quantity: int
    price: float
    retail_price: Optional[float] = None
    discount_pct: Optional[float] = None
    extra_discount_pct: Optional[float] = None
    trade_price: Optional[float] = None
    is_cut_rate: Optional[bool] = None


class PurchaseCreate(BaseModel):
    id: Optional[int] = None
    date: Optional[str] = None
    supplier_id: Optional[int] = 0
    supplier_name: Optional[str] = ""
    total: Optional[float] = 0.0
    items: list[PurchaseItem] = []


class PurchaseOut(BaseModel):
    id: int
    date: str
    supplier_id: int
    supplier_name: str
    total: float
    items: list[PurchaseItem]

    class Config:
        from_attributes = True


class TransactionItem(BaseModel):
    id: int
    quantity: int


class TransactionCreate(BaseModel):
    id: Optional[int] = None
    date: Optional[str] = None
    user_id: Optional[int] = 0
    customer_id: Optional[int] = 0
    till: Optional[int] = 0
    status: Optional[int] = 1
    total: Optional[float] = 0.0
    paid: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    items: list[TransactionItem] = []


class TransactionOut(BaseModel):
    id: int
    date: str
    user_id: int
    customer_id: int
    till: int
    status: int
    total: float
    paid: float
    discount: float
    items: list[TransactionItem]

    class Config:
        from_attributes = True
