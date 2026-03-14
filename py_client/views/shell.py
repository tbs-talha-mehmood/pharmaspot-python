from PyQt5 import QtWidgets, QtCore
from .products import ProductsView
from .pos import POSView
from .companies import CompaniesView
from .customers import CustomersView
from .settings import SettingsView
from .dashboard import DashboardView
from .purchases import PurchasesView
from .suppliers import SuppliersView
from .transactions import TransactionsView
from .reports import ReportsView


class ShellView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user = None
        self._build()

    def _build(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav = QtWidgets.QListWidget()
        self.nav.setObjectName("sideNav")
        self.nav.setFixedWidth(200)
        self.nav.setSpacing(2)
        layout.addWidget(self.nav)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.dashboard = DashboardView(self.api)
        self.pos = POSView(self.api)
        self.products = ProductsView(self.api)
        self.companies = CompaniesView(self.api)
        self.suppliers = SuppliersView(self.api)
        self.customers = CustomersView(self.api)
        self.settings = SettingsView(self.api)
        self.purchases = PurchasesView(self.api)
        self.transactions = TransactionsView(self.api)
        self.reports = ReportsView(self.api)

        try:
            self.purchases.inventory_changed.connect(self.products.refresh_inventory)
        except Exception:
            pass

        items = [
            ("Dashboard", self.dashboard),
            ("Point of Sale", self.pos),
            ("Products", self.products),
            ("Companies", self.companies),
            ("Suppliers", self.suppliers),
            ("Customers", self.customers),
            ("Purchases", self.purchases),
            ("Transactions", self.transactions),
            ("Reports", self.reports),
            ("Settings", self.settings),
        ]

        self._nav_row_by_label = {}
        for label, widget in items:
            index = self.stack.addWidget(widget)
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, index)
            self.nav.addItem(item)
            self._nav_row_by_label[label] = self.nav.count() - 1

        self.nav.currentItemChanged.connect(self._on_nav_change)
        self.nav.setCurrentRow(0)

    def _on_nav_change(self, current, previous):
        if current is None:
            return
        index = current.data(QtCore.Qt.UserRole)
        if isinstance(index, int):
            self.stack.setCurrentIndex(index)
            widget = self.stack.widget(index)
            try:
                if widget is self.products and hasattr(widget, "refresh_inventory"):
                    widget.refresh_inventory()
                elif hasattr(widget, "refresh"):
                    widget.refresh()
                if widget is self.products and hasattr(widget, "focus_search"):
                    QtCore.QTimer.singleShot(0, widget.focus_search)
                if widget is self.companies and hasattr(widget, "focus_search"):
                    QtCore.QTimer.singleShot(0, widget.focus_search)
                if widget is self.customers and hasattr(widget, "focus_search"):
                    QtCore.QTimer.singleShot(0, widget.focus_search)
                if widget is self.suppliers and hasattr(widget, "focus_search"):
                    QtCore.QTimer.singleShot(0, widget.focus_search)
                if widget is self.pos and hasattr(widget, "_focus_search"):
                    QtCore.QTimer.singleShot(0, widget._focus_search)
            except Exception:
                pass

    def set_user(self, user: dict):
        self.user = user

        try:
            uid = int(user.get("id", 0) or 0)
        except Exception:
            uid = 0
        uname = str(user.get("username", "") or "").strip().lower()
        is_admin = bool(uid == 1 or uname == "admin")

        can_products = bool(user.get("perm_products", False) or is_admin)
        can_see_cost = bool(user.get("perm_see_cost", False) or is_admin)
        can_settings = bool(
            user.get("perm_settings", False)
            or user.get("perm_users", False)
            or is_admin
        )

        def _set_nav_visible(label: str, visible: bool):
            row = self._nav_row_by_label.get(label)
            if row is None:
                return
            item = self.nav.item(row)
            if item is not None:
                item.setHidden(not visible)

        _set_nav_visible("Products", can_products)
        _set_nav_visible("Dashboard", can_see_cost)
        _set_nav_visible("Companies", True)
        _set_nav_visible("Suppliers", True)
        _set_nav_visible("Customers", True)
        _set_nav_visible("Purchases", True)
        _set_nav_visible("Transactions", True)
        _set_nav_visible("Reports", can_see_cost)
        _set_nav_visible("Settings", can_settings)

        # Pass user details into child views
        self.pos.set_user(user)
        if hasattr(self.customers, "set_user"):
            self.customers.set_user(user)
        if hasattr(self.suppliers, "set_user"):
            self.suppliers.set_user(user)
        if hasattr(self.settings, "set_user"):
            self.settings.set_user(user)
        if hasattr(self.purchases, "set_user"):
            self.purchases.set_user(user)
        if hasattr(self.transactions, "set_user"):
            self.transactions.set_user(user)
        if hasattr(self.reports, "set_user"):
            self.reports.set_user(user)
        if hasattr(self.dashboard, "set_user"):
            self.dashboard.set_user(user)
