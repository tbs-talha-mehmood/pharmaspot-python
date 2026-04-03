from PyQt5 import QtWidgets, QtCore
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


class ProductsView(QtWidgets.QWidget):
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
        self.filter_company = QtWidgets.QComboBox()
        self.filter_company.setMinimumWidth(200)
        self.filter_company.addItem("All companies", 0)
        self.chk_inactive = QtWidgets.QCheckBox("Show inactive")
        self.btn_add = QtWidgets.QPushButton("Add Product")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Deactivate")
        set_secondary(self.btn_edit)
        set_accent(self.btn_add)
        set_danger(self.btn_delete)
        header.addWidget(self.filter_company)
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        header.addWidget(self.chk_inactive)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search by name")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(360)
        self.search.installEventFilter(self)
        header.addWidget(self.search)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Qty", "Price", "Company", "Expiry"])
        configure_table(self.table, stretch_last=False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
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

        self.btn_add.clicked.connect(self.add_product_dialog)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.filter_company.currentIndexChanged.connect(self._on_filter_changed)
        self.chk_inactive.stateChanged.connect(self._on_filter_changed)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self._on_search_changed)
        QtCore.QTimer.singleShot(0, self.refresh)
        self._page = 1
        self._pages = 1
        polish_controls(self)
        self.table.itemSelectionChanged.connect(self._sync_action_state)
        self._sync_action_state()

    def focus_search(self):
        self.search.setFocus(QtCore.Qt.OtherFocusReason)
        self.search.selectAll()

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QtCore.QEvent.FocusIn:
            QtCore.QTimer.singleShot(0, self.search.selectAll)
        return super().eventFilter(obj, event)

    def _sync_action_state(self):
        existing = self._selected_product()
        has_sel = existing is not None
        is_active = bool((existing or {}).get("is_active", True))
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_delete.setText("Reactivate" if (has_sel and not is_active) else "Deactivate")
        if has_sel and not is_active:
            self.btn_delete.setProperty("danger", False)
            self.btn_delete.setProperty("accent", True)
        else:
            self.btn_delete.setProperty("accent", False)
            self.btn_delete.setProperty("danger", True)
        self.btn_delete.style().unpolish(self.btn_delete)
        self.btn_delete.style().polish(self.btn_delete)
        self.btn_delete.update()

    def _on_search_changed(self):
        self._search_timer.stop()
        if len(self.search.text().strip()) >= 3:
            self._search_timer.start()
        else:
            self._page = 1
            self.refresh()

    def _on_filter_changed(self):
        self._page = 1
        self.refresh()

    def refresh_inventory(self):
        self._page = 1
        self.refresh()

    def refresh(self):
        try:
            selected_id = int(self.filter_company.currentData() or 0)
            companies = self.api.companies(include_inactive=self.chk_inactive.isChecked())
            self._rebuild_company_filter(companies, selected_id)
            filter_id = int(self.filter_company.currentData() or 0)
            data = self.api.products_page(
                company_id=filter_id,
                q=self.search.text().strip(),
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
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(p.get("quantity", 0))))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(f"{float(p.get('price', 0.0) or 0.0):.2f}"))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(p.get("company_name", "")))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(str(p.get("expirationDate", "") or "")))
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)
        self._sync_action_state()

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        if self._page < self._pages:
            self._page += 1
            self.refresh()

    def _rebuild_company_filter(self, companies, current_id):
        self.filter_company.blockSignals(True)
        self.filter_company.clear()
        self.filter_company.addItem("All companies", 0)
        for c in companies or []:
            self.filter_company.addItem(c.get("name", ""), int(c.get("id")))
        if current_id:
            idx = self.filter_company.findData(int(current_id))
            if idx >= 0:
                self.filter_company.setCurrentIndex(idx)
        self.filter_company.blockSignals(False)

    def _product_dialog(self, title: str, existing: dict | None = None):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(title)
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        name.setPlaceholderText("Product name")
        price = QtWidgets.QDoubleSpinBox()
        price.setMaximum(10**9)
        price.setDecimals(2)
        expiry = QtWidgets.QLineEdit()
        expiry.setPlaceholderText("YYYY-MM-DD (optional)")
        company = QtWidgets.QComboBox()
        company.setEditable(True)
        try:
            company.clear()
            company.addItem("Select or type name", 0)
            for c in self.api.companies() or []:
                company.addItem(c.get("name", ""), int(c.get("id")))
        except Exception:
            pass
        if existing:
            name.setText(existing.get("name", ""))
            price.setValue(float(existing.get("price", 0.0) or 0.0))
            expiry.setText(str(existing.get("expirationDate", "") or ""))
            cid = int(existing.get("company_id") or 0)
            if cid:
                idx = company.findData(cid)
                if idx >= 0:
                    company.setCurrentIndex(idx)
            elif existing.get("company_name"):
                company.setCurrentText(existing.get("company_name"))
        form.addRow("Name", name)
        form.addRow("Price", price)
        form.addRow("Expiry", expiry)
        form.addRow("Company", company)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=440, fixed=True)
        return d, name, price, company, expiry

    def _selected_product(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        pid_item = self.table.item(r, 0)
        if not pid_item:
            return None
        try:
            pid = int(pid_item.text())
        except Exception:
            return None
        try:
            return self.api.product_get(pid)
        except Exception:
            return None

    def add_product_dialog(self):
        d, name, price, company, expiry = self._product_dialog("Add Product")
        while d.exec_() == QtWidgets.QDialog.Accepted:
            try:
                payload = self._payload_from_form(name, price, company, expiry)
                resp = self.api.product_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    raise Exception(str(resp.get("detail")))
                self.refresh()
                return
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def edit_selected(self):
        existing = self._selected_product()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a product row first")
            return
        d, name, price, company, expiry = self._product_dialog("Edit Product", existing)
        while d.exec_() == QtWidgets.QDialog.Accepted:
            try:
                payload = self._payload_from_form(name, price, company, expiry)
                payload["id"] = int(existing.get("id"))
                resp = self.api.product_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    raise Exception(str(resp.get("detail")))
                self.refresh()
                return
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def delete_selected(self):
        existing = self._selected_product()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a product row first")
            return
        is_active = bool(existing.get("is_active", True))
        try:
            if is_active:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Deactivate this product?") != QtWidgets.QMessageBox.Yes:
                    return
                self.api.product_delete(int(existing.get("id")))
                QtWidgets.QMessageBox.information(self, "Deactivated", "Product has been deactivated.")
            else:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Reactivate this product?") != QtWidgets.QMessageBox.Yes:
                    return
                payload = {
                    "id": int(existing.get("id")),
                    "name": str(existing.get("name", "") or ""),
                    "price": float(existing.get("price", 0.0) or 0.0),
                    "company_id": int(existing.get("company_id", 0) or 0),
                    "quantity": int(existing.get("quantity", 0) or 0),
                    "expirationDate": str(existing.get("expirationDate", "") or ""),
                    "img": str(existing.get("img", "") or ""),
                    "discount_pct": float(existing.get("discount_pct", 0.0) or 0.0),
                    "trade_price": float(existing.get("trade_price", 0.0) or 0.0),
                }
                resp = self.api.product_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                QtWidgets.QMessageBox.information(self, "Reactivated", "Product has been reactivated.")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _payload_from_form(self, name, price, company, expiry):
        try:
            company_id = int(company.currentData() or 0)
        except Exception:
            company_id = 0
        company_name = (company.currentText() or "").strip()
        if company_name.lower() == "select or type name":
            company_name = ""
        name_val = name.text().strip()
        if not name_val:
            raise ValueError("Name is required")
        if price.value() <= 0:
            raise ValueError("Price must be greater than 0")
        if company_id == 0:
            if not company_name:
                raise ValueError("Company is required")
            created = self.api.company_upsert({"name": company_name})
            if isinstance(created, dict) and created.get("detail") and not created.get("id"):
                raise ValueError(str(created.get("detail")))
            try:
                company_id = int((created or {}).get("id", 0) or 0)
            except Exception:
                company_id = 0
            if company_id == 0:
                raise ValueError("Company is required")
        return {
            "name": name_val,
            "price": price.value(),
            "company_id": company_id,
            "expirationDate": expiry.text().strip(),
        }





