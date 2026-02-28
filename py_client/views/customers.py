from PyQt5 import QtWidgets
from .ui_common import (
    apply_form_layout,
    apply_header_layout,
    apply_page_layout,
    configure_table,
    fit_dialog_to_contents,
    polish_controls,
    set_accent,
    set_danger,
    set_secondary,
)


class CustomersView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)
        header = QtWidgets.QHBoxLayout()
        apply_header_layout(header)
        self.chk_inactive = QtWidgets.QCheckBox("Show inactive")
        self.btn_add = QtWidgets.QPushButton("Add Customer")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        set_secondary(self.btn_edit)
        set_accent(self.btn_add)
        set_danger(self.btn_delete)
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        header.addWidget(self.chk_inactive)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Phone", "Email", "Address"])
        configure_table(self.table, stretch_last=False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table)

        pager = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("Prev")
        self.btn_next = QtWidgets.QPushButton("Next")
        set_secondary(self.btn_prev, self.btn_next)
        self.page_label = QtWidgets.QLabel("Page 1 / 1")
        self.page_label.setObjectName("mutedLabel")
        pager.addWidget(self.btn_prev)
        pager.addWidget(self.btn_next)
        pager.addWidget(self.page_label)
        pager.addStretch(1)
        layout.addLayout(pager)

        self.btn_add.clicked.connect(self.add_dialog)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.chk_inactive.stateChanged.connect(self._on_filter_changed)
        self._page = 1
        self._pages = 1
        polish_controls(self)

    def refresh(self):
        try:
            data = self.api.customers_page(
                include_inactive=self.chk_inactive.isChecked(),
                page=self._page,
                page_size=25,
            )
            items = data.get("items", [])
            self._pages = int(data.get("pages", 1) or 1)
            self._page = max(1, min(int(data.get("page", self._page) or self._page), self._pages))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.table.setRowCount(0)
        for p in items:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(p.get("id"))))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(p.get("name", "")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(p.get("phone", "")))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(p.get("email", "")))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(p.get("address", "")))
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)

    def _on_filter_changed(self):
        self._page = 1
        self.refresh()

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        if self._page < self._pages:
            self._page += 1
            self.refresh()

    def add_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add Customer")
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        name.setPlaceholderText("Customer name")
        phone = QtWidgets.QLineEdit()
        phone.setPlaceholderText("Phone number")
        email = QtWidgets.QLineEdit()
        email.setPlaceholderText("Email")
        address = QtWidgets.QLineEdit()
        address.setPlaceholderText("Address")
        form.addRow("Name", name)
        form.addRow("Phone", phone)
        form.addRow("Email", email)
        form.addRow("Address", address)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=460, fixed=True)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "name": name.text().strip(),
                "phone": phone.text().strip(),
                "email": email.text().strip(),
                "address": address.text().strip(),
            }
            try:
                if not payload["name"]:
                    raise ValueError("Name is required")
                self.api.customer_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _selected_customer(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        cid_item = self.table.item(r, 0)
        if not cid_item:
            return None
        try:
            cid = int(cid_item.text())
        except Exception:
            return None
        try:
            return self.api.customer_get(cid)
        except Exception:
            return None

    def _customer_dialog(self, title: str, existing: dict | None = None):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(title)
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        phone = QtWidgets.QLineEdit()
        email = QtWidgets.QLineEdit()
        address = QtWidgets.QLineEdit()
        if existing:
            name.setText(existing.get("name", ""))
            phone.setText(existing.get("phone", ""))
            email.setText(existing.get("email", ""))
            address.setText(existing.get("address", ""))
        form.addRow("Name", name)
        form.addRow("Phone", phone)
        form.addRow("Email", email)
        form.addRow("Address", address)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=460, fixed=True)
        return d, name, phone, email, address

    def edit_selected(self):
        existing = self._selected_customer()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a customer row first")
            return
        d, name, phone, email, address = self._customer_dialog("Edit Customer", existing)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "id": int(existing.get("id")),
                "name": name.text().strip(),
                "phone": phone.text().strip(),
                "email": email.text().strip(),
                "address": address.text().strip(),
            }
            try:
                if not payload["name"]:
                    raise ValueError("Name is required")
                self.api.customer_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def delete_selected(self):
        existing = self._selected_customer()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a customer row first")
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this customer?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.api.customer_delete(int(existing.get("id")))
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
