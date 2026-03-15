from PyQt5 import QtWidgets, QtCore
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
        self.btn_edit = QtWidgets.QPushButton("Edit User")
        set_accent(self.btn_add)
        set_secondary(self.btn_edit)
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_edit)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Username", "Fullname"])
        configure_table(self.table)
        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self.add_user_dialog)
        self.btn_edit.clicked.connect(self.edit_user_dialog)
        self.table.itemDoubleClicked.connect(self._edit_user_from_row)
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
            id_item = QtWidgets.QTableWidgetItem(str(u.get("id")))
            # Store full user payload to drive edit dialog.
            id_item.setData(QtCore.Qt.UserRole, u)
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(u.get("username", "")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(u.get("fullname", "")))

    def _open_user_dialog(self, user: dict | None = None):
        d = QtWidgets.QDialog(self)
        is_edit = bool(user)
        d.setWindowTitle("Edit User" if is_edit else "Add User")
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        username = QtWidgets.QLineEdit()
        username.setPlaceholderText("username")
        fullname = QtWidgets.QLineEdit()
        fullname.setPlaceholderText("Full name")
        password = QtWidgets.QLineEdit()
        password.setEchoMode(QtWidgets.QLineEdit.Password)
        if is_edit:
            password.setPlaceholderText("Leave blank to keep current password")
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

        # Pre-fill when editing an existing user
        if is_edit:
            username.setText(str(user.get("username", "") or ""))
            username.setEnabled(False)
            fullname.setText(str(user.get("fullname", "") or ""))
            p_products.setChecked(bool(user.get("perm_products", False)))
            p_transactions.setChecked(bool(user.get("perm_transactions", False)))
            p_users.setChecked(bool(user.get("perm_users", False)))
            p_settings.setChecked(bool(user.get("perm_settings", False)))
            p_see_cost.setChecked(bool(user.get("perm_see_cost", False)))
            p_give_discount.setChecked(bool(user.get("perm_give_discount", False)))
            p_edit_invoice.setChecked(bool(user.get("perm_edit_invoice", False)))
            p_delete_payment.setChecked(bool(user.get("perm_delete_payment", False)))

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

    def add_user_dialog(self):
        self._open_user_dialog(None)

    def _selected_user_payload(self) -> dict | None:
        r = self.table.currentRow()
        if r < 0:
            return None
        item = self.table.item(r, 0)
        if not item:
            return None
        data = item.data(QtCore.Qt.UserRole)
        return data if isinstance(data, dict) else None

    def edit_user_dialog(self):
        user = self._selected_user_payload()
        if not user:
            QtWidgets.QMessageBox.information(self, "Select User", "Select a user row to edit.")
            return
        self._open_user_dialog(user)

    def _edit_user_from_row(self, item: QtWidgets.QTableWidgetItem):
        # Double-click on any cell edits that user.
        row = item.row()
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        data = id_item.data(QtCore.Qt.UserRole)
        if isinstance(data, dict):
            self._open_user_dialog(data)
