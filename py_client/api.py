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
    def products(self):
        return self.get("/api/products/all").json()

    def product_get(self, pid: int):
        return self.get(f"/api/products/product/{pid}").json()

    def product_upsert(self, payload: dict):
        return self.post_json("/api/products/product", payload).json()

    def product_delete(self, pid: int):
        return requests.delete(self.base_url + f"/api/products/product/{pid}").json()

    # Customers
    def customers(self):
        return self.get("/api/customers/all").json()

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

    # Companies
    def companies(self, include_inactive: bool = False):
        suffix = "?include_inactive=true" if include_inactive else ""
        return self.get(f"/api/companies/all{suffix}").json()

    def company_upsert(self, payload: dict):
        r = self.post_json("/api/companies/company", payload)
        try:
            return r.json()
        except ValueError:
            return {"detail": (r.text or f"HTTP {r.status_code}")}

    def company_delete(self, cid: int):
        return requests.delete(self.base_url + f"/api/companies/company/{cid}").json()

    # Purchases
    def purchases_list(self):
        return self.get("/api/purchases/list").json()

    def purchase_new(self, payload: dict):
        return self.post_json("/api/purchases/new", payload).json()

    # Transactions
    def transactions_list(self):
        return self.get("/api/transactions/list").json()

    def transaction_new(self, payload: dict):
        return self.post_json("/api/transactions/new", payload).json()
