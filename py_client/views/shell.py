from PyQt5 import QtWidgets, QtCore
from .users import UsersView
from .products import ProductsView
from .pos import POSView
from .companies import CompaniesView
from .customers import CustomersView
from .settings import SettingsView
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

        self.nav = QtWidgets.QListWidget()
        self.nav.setFixedWidth(200)
        layout.addWidget(self.nav)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.pos = POSView(self.api)
        self.products = ProductsView(self.api)
        self.companies = CompaniesView(self.api)
        self.customers = CustomersView(self.api)
        self.users = UsersView(self.api)
        self.settings = SettingsView(self.api)
        self.purchases = PurchasesView(self.api)
        self.transactions = TransactionsView(self.api)
        self.reports = ReportsView(self.api)

        items = [
            ("Point of Sale", self.pos),
            ("Products", self.products),
            ("Companies", self.companies),
            ("Customers", self.customers),
            ("Users", self.users),
            ("Settings", self.settings),
            ("Purchases", self.purchases),
            ("Transactions", self.transactions),
            ("Reports", self.reports),
        ]

        for label, widget in items:
            index = self.stack.addWidget(widget)
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, index)
            self.nav.addItem(item)

        self.nav.currentItemChanged.connect(self._on_nav_change)
        self.nav.setCurrentRow(0)

    def _on_nav_change(self, current, previous):
        if current is None:
            return
        index = current.data(QtCore.Qt.UserRole)
        if isinstance(index, int):
            self.stack.setCurrentIndex(index)

    def set_user(self, user: dict):
        self.user = user
        # apply permissions by enabling/disabling tabs
        self.nav.item(1).setHidden(not user.get("perm_products", False))
        self.nav.item(2).setHidden(False)  # Companies visible for now
        self.nav.item(3).setHidden(False)  # Customers visible for now
        self.nav.item(4).setHidden(not user.get("perm_users", False))
        self.nav.item(5).setHidden(not user.get("perm_settings", False))
        # pass user to POS for user_id in transactions
        self.pos.set_user(user)
        # Purchases/Transactions/Reports currently visible to all logged users
        self.nav.item(6).setHidden(False)
        self.nav.item(7).setHidden(False)
        self.nav.item(8).setHidden(False)
