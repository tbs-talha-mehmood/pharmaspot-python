from PyQt5 import QtWidgets
from .ui_common import (
    apply_form_layout,
    apply_header_layout,
    apply_page_layout,
    configure_table,
    fit_dialog_to_contents,
    polish_controls,
    set_accent,
    set_secondary,
)


class UsersView(QtWidgets.QWidget):
    def __init__(self, api, *, auto_refresh: bool = True):
        super().__init__()
        self.api = api
        self._build()
        if auto_refresh:
            self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)
        header = QtWidgets.QHBoxLayout()
        apply_header_layout(header)
        self.btn_add = QtWidgets.QPushButton("Add User")
        set_accent(self.btn_add)
        header.addWidget(self.btn_add)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Username", "Fullname"])
        configure_table(self.table)
        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self.add_user_dialog)
        polish_controls(self)

    def refresh(self):
        try:
            users = self.api.users_all()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return

        self.table.setRowCount(0)
        for u in users:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(u.get("id"))))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(u.get("username", "")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(u.get("fullname", "")))

    def add_user_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add User")
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        username = QtWidgets.QLineEdit()
        username.setPlaceholderText("username")
        fullname = QtWidgets.QLineEdit()
        fullname.setPlaceholderText("Full name")
        password = QtWidgets.QLineEdit(); password.setEchoMode(QtWidgets.QLineEdit.Password)
        p_products = QtWidgets.QCheckBox()
        p_transactions = QtWidgets.QCheckBox()
        p_users = QtWidgets.QCheckBox()
        p_settings = QtWidgets.QCheckBox()
        p_see_cost = QtWidgets.QCheckBox()
        p_give_discount = QtWidgets.QCheckBox()
        p_edit_invoice = QtWidgets.QCheckBox()
        p_delete_payment = QtWidgets.QCheckBox()
        form.addRow("Username", username)
        form.addRow("Fullname", fullname)
        form.addRow("Password", password)
        form.addRow("Products", p_products)
        form.addRow("Transactions", p_transactions)
        form.addRow("Users", p_users)
        form.addRow("Settings", p_settings)
        form.addRow("Can See Cost/Profit", p_see_cost)
        form.addRow("Can Give Discount", p_give_discount)
        form.addRow("Can Edit Invoices", p_edit_invoice)
        form.addRow("Can Delete Payments", p_delete_payment)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=420, fixed=True)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "username": username.text().strip(),
                "fullname": fullname.text().strip(),
                "password": password.text(),
                "perm_products": p_products.isChecked(),
                "perm_transactions": p_transactions.isChecked(),
                "perm_users": p_users.isChecked(),
                "perm_settings": p_settings.isChecked(),
                "perm_see_cost": p_see_cost.isChecked(),
                "perm_give_discount": p_give_discount.isChecked(),
                "perm_edit_invoice": p_edit_invoice.isChecked(),
                "perm_delete_payment": p_delete_payment.isChecked(),
            }
            try:
                self.api.user_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
