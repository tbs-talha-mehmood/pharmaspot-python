import os
import requests


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, **kwargs):
        return requests.get(self.base_url + path, **kwargs)

    def post_json(self, path: str, data: dict):
        return requests.post(self.base_url + path, json=data)

    def post_form(self, path: str, data: dict, files=None):
        return requests.post(self.base_url + path, data=data, files=files)

    # Users
    def users_check(self):
        return self.get("/api/users/check").json()

    def login(self, username: str, password: str):
        r = self.post_json("/api/users/login", {"username": username, "password": password})
        return r.json()

    def users_all(self):
        return self.get("/api/users/all").json()

    def user_get(self, user_id: int):
        return self.get(f"/api/users/user/{user_id}").json()

    def user_upsert(self, payload: dict):
        return self.post_json("/api/users/post", payload).json()

    # Products (JSON CRUD)
    def products(self, company_id: int = 0, q: str = "", include_inactive: bool = False):
        params = []
        if company_id:
            params.append(f"company_id={int(company_id)}")
        if q:
            params.append(f"q={q}")
        if include_inactive:
            params.append("include_inactive=true")
        suffix = f"?{'&'.join(params)}" if params else ""
        return self.get(f"/api/products/all{suffix}").json()

    def products_page(
        self,
        company_id: int = 0,
        q: str = "",
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 25,
    ):
        params = [f"page={int(page)}", f"page_size={int(page_size)}"]
        if company_id:
            params.append(f"company_id={int(company_id)}")
        if q:
            params.append(f"q={q}")
        if include_inactive:
            params.append("include_inactive=true")
        suffix = f"?{'&'.join(params)}"
        return self.get(f"/api/products/page{suffix}").json()

    def product_get(self, pid: int):
        return self.get(f"/api/products/product/{pid}").json()

    def product_upsert(self, payload: dict):
        return self.post_json("/api/products/product", payload).json()

    def product_delete(self, pid: int):
        return requests.delete(self.base_url + f"/api/products/product/{pid}").json()

    # Customers
    def customers(self, include_inactive: bool = False):
        suffix = "?include_inactive=true" if include_inactive else ""
        return self.get(f"/api/customers/all{suffix}").json()

    def customers_page(self, include_inactive: bool = False, q: str = "", page: int = 1, page_size: int = 25):
        params = [f"page={int(page)}", f"page_size={int(page_size)}"]
        if q:
            params.append(f"q={q}")
        if include_inactive:
            params.append("include_inactive=true")
        suffix = f"?{'&'.join(params)}"
        return self.get(f"/api/customers/page{suffix}").json()

    def customer_get(self, cid: int):
        return self.get(f"/api/customers/customer/{cid}").json()

    def customer_upsert(self, payload: dict):
        return self.post_json("/api/customers/customer", payload).json()

    def customer_delete(self, cid: int):
        return requests.delete(self.base_url + f"/api/customers/customer/{cid}").json()

    # Settings
    def settings_all(self):
        return self.get("/api/settings/all").json()

    def settings_map(self):
        return self.get("/api/settings/get").json()

    def setting_set(self, key: str, value: str):
        return self.post_json("/api/settings/set", {"key": key, "value": value}).json()

    def period_lock_get(self):
        return self.get("/api/settings/period_lock").json()

    def period_lock_set(self, lock_until: str | None):
        return self.post_json("/api/settings/period_lock", {"lock_until": lock_until}).json()

    # Companies
    def companies(self, include_inactive: bool = False):
        suffix = "?include_inactive=true" if include_inactive else ""
        return self.get(f"/api/companies/all{suffix}").json()

    def companies_page(self, include_inactive: bool = False, q: str = "", page: int = 1, page_size: int = 25):
        params = [f"page={int(page)}", f"page_size={int(page_size)}"]
        if q:
            params.append(f"q={q}")
        if include_inactive:
            params.append("include_inactive=true")
        suffix = f"?{'&'.join(params)}"
        return self.get(f"/api/companies/page{suffix}").json()

    def company_upsert(self, payload: dict):
        r = self.post_json("/api/companies/company", payload)
        try:
            return r.json()
        except ValueError:
            return {"detail": (r.text or f"HTTP {r.status_code}")}

    def company_delete(self, cid: int):
        return requests.delete(self.base_url + f"/api/companies/company/{cid}").json()

    # Suppliers
    def suppliers(self, include_inactive: bool = False):
        suffix = "?include_inactive=true" if include_inactive else ""
        return self.get(f"/api/suppliers/all{suffix}").json()

    def suppliers_page(self, include_inactive: bool = False, page: int = 1, page_size: int = 25):
        params = [f"page={int(page)}", f"page_size={int(page_size)}"]
        if include_inactive:
            params.append("include_inactive=true")
        suffix = f"?{'&'.join(params)}"
        return self.get(f"/api/suppliers/page{suffix}").json()

    def supplier_upsert(self, payload: dict):
        r = self.post_json("/api/suppliers/supplier", payload)
        try:
            return r.json()
        except ValueError:
            return {"detail": (r.text or f"HTTP {r.status_code}")}

    def supplier_delete(self, sid: int):
        return requests.delete(self.base_url + f"/api/suppliers/supplier/{sid}").json()

    # Purchases
    def purchases_list(self):
        return self.get("/api/purchases/list").json()

    def purchases_page(self, page: int = 1, page_size: int = 25):
        suffix = f"?page={int(page)}&page_size={int(page_size)}"
        return self.get(f"/api/purchases/page{suffix}").json()

    def purchase_get(self, purchase_id: int):
        return self.get(f"/api/purchases/purchase/{int(purchase_id)}").json()

    def purchase_new(self, payload: dict):
        return self.post_json("/api/purchases/new", payload).json()

    def purchase_update(self, purchase_id: int, payload: dict):
        return requests.put(self.base_url + f"/api/purchases/purchase/{purchase_id}", json=payload).json()

    def purchase_delete(self, purchase_id: int):
        return requests.delete(self.base_url + f"/api/purchases/purchase/{int(purchase_id)}").json()

    # Held Sales
    def held_sales_list(self):
        return self.get("/api/held_sales/list").json()

    def held_sale_new(self, payload: dict):
        return self.post_json("/api/held_sales/new", payload).json()

    def held_sale_delete(self, hold_id: int):
        return requests.delete(self.base_url + f"/api/held_sales/held_sale/{hold_id}").json()

    # Transactions
    def transactions_list(self):
        return self.get("/api/transactions/list").json()

    def transactions_page(
        self,
        start_date: str = "",
        end_date: str = "",
        user_id: int = 0,
        page: int = 1,
        page_size: int = 25,
    ):
        params = [f"page={int(page)}", f"page_size={int(page_size)}"]
        if start_date:
            params.append(f"start_date={start_date}")
        if end_date:
            params.append(f"end_date={end_date}")
        if int(user_id or 0) > 0:
            params.append(f"user_id={int(user_id)}")
        suffix = f"?{'&'.join(params)}"
        return self.get(f"/api/transactions/page{suffix}").json()

    def transactions_by_customer(self, customer_id: int):
        return self.get(f"/api/transactions/customer/{int(customer_id)}/list").json()

    def customer_payment_apply(self, customer_id: int, amount: float, user_id: int = 0, date: str | None = None):
        payload = {"amount": float(amount), "user_id": int(user_id or 0)}
        if date:
            payload["date"] = str(date)
        return self.post_json(f"/api/transactions/customer/{int(customer_id)}/payment", payload).json()

    def transaction_get(self, tid: int):
        return self.get(f"/api/transactions/transaction/{int(tid)}").json()

    def transaction_payments(self, tid: int):
        return self.get(f"/api/transactions/transaction/{int(tid)}/payments").json()

    def transaction_payments_list(self):
        return self.get("/api/transactions/payments").json()

    def transaction_payment_update(self, tid: int, payment_id: int, amount: float):
        return requests.put(
            self.base_url + f"/api/transactions/transaction/{int(tid)}/payment/{int(payment_id)}",
            json={"amount": float(amount)},
        ).json()

    def transaction_new(self, payload: dict):
        return self.post_json("/api/transactions/new", payload).json()

    def transaction_update(self, tid: int, payload: dict):
        return requests.put(self.base_url + f"/api/transactions/transaction/{int(tid)}", json=payload).json()

    def transaction_delete(self, tid: int):
        return requests.delete(self.base_url + f"/api/transactions/transaction/{int(tid)}").json()
