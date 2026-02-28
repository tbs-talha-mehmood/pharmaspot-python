from PyQt5 import QtWidgets, QtCore
from .products import ProductsView
from .pos import POSView
from .companies import CompaniesView
from .customers import CustomersView
from .settings import SettingsView
from .dashboard import DashboardView
from .purchases import PurchasesView
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
                if widget is self.pos and hasattr(widget, "_focus_search"):
                    QtCore.QTimer.singleShot(0, widget._focus_search)
            except Exception:
                pass

    def set_user(self, user: dict):
        self.user = user
        def _set_nav_visible(label: str, visible: bool):
            row = self._nav_row_by_label.get(label)
            if row is None:
                return
            item = self.nav.item(row)
            if item is not None:
                item.setHidden(not visible)

        _set_nav_visible("Products", bool(user.get("perm_products", False)))
        _set_nav_visible("Dashboard", True)
        _set_nav_visible("Companies", True)
        _set_nav_visible("Customers", True)
        _set_nav_visible("Purchases", True)
        _set_nav_visible("Transactions", True)
        _set_nav_visible("Reports", True)
        _set_nav_visible(
            "Settings",
            bool(user.get("perm_settings", False) or user.get("perm_users", False)),
        )
        # pass user to POS for user_id in transactions
        self.pos.set_user(user)
        if hasattr(self.settings, "set_user"):
            self.settings.set_user(user)
