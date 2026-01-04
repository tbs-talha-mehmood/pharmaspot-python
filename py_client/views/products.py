from PyQt5 import QtWidgets, QtCore


class ProductsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Products"))
        self.filter_company = QtWidgets.QComboBox()
        self.filter_company.setMinimumWidth(200)
        self.filter_company.addItem("All companies", 0)
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_add = QtWidgets.QPushButton("Add Product")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        header.addWidget(self.filter_company)
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search by name")
        self.search.setMinimumWidth(360)
        header.addWidget(self.search)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Barcode", "Name", "Qty", "Price", "Company"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        pager = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("Prev")
        self.btn_next = QtWidgets.QPushButton("Next")
        self.page_label = QtWidgets.QLabel("Page 1 / 1")
        pager.addWidget(self.btn_prev)
        pager.addWidget(self.btn_next)
        pager.addWidget(self.page_label)
        pager.addStretch(1)
        layout.addLayout(pager)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_add.clicked.connect(self.add_product_dialog)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.filter_company.currentIndexChanged.connect(self._on_filter_changed)
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
            companies = self.api.companies()
            self._rebuild_company_filter(companies, selected_id)
            filter_id = int(self.filter_company.currentData() or 0)
            data = self.api.products_page(
                company_id=filter_id,
                q=self.search.text().strip(),
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
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(p.get("barcode", ""))))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(p.get("name", "")))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(str(p.get("quantity", 0))))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(str(p.get("price", 0.0))))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(p.get("company_name", "")))
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)

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
        name = QtWidgets.QLineEdit()
        barcode = QtWidgets.QLineEdit()
        price = QtWidgets.QDoubleSpinBox()
        price.setMaximum(10**9)
        price.setDecimals(2)
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
            barcode.setText(str(existing.get("barcode", "") or ""))
            price.setValue(float(existing.get("price", 0.0) or 0.0))
            cid = int(existing.get("company_id") or 0)
            if cid:
                idx = company.findData(cid)
                if idx >= 0:
                    company.setCurrentIndex(idx)
            elif existing.get("company_name"):
                company.setCurrentText(existing.get("company_name"))
        form.addRow("Name", name)
        form.addRow("Barcode", barcode)
        form.addRow("Price", price)
        form.addRow("Company", company)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        return d, name, barcode, price, company

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
        d, name, barcode, price, company = self._product_dialog("Add Product")
        if d.exec_() == QtWidgets.QDialog.Accepted:
            try:
                payload = self._payload_from_form(name, barcode, price, company)
                self.api.product_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def edit_selected(self):
        existing = self._selected_product()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a product row first")
            return
        d, name, barcode, price, company = self._product_dialog("Edit Product", existing)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            try:
                payload = self._payload_from_form(name, barcode, price, company)
                payload["id"] = int(existing.get("id"))
                self.api.product_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def delete_selected(self):
        existing = self._selected_product()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a product row first")
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this product?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.api.product_delete(int(existing.get("id")))
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _payload_from_form(self, name, barcode, price, company):
        company_id = int(company.currentData() or 0)
        company_name = company.currentText().strip()
        if company_id == 0 and company_name:
            try:
                created = self.api.company_upsert({"name": company_name})
                if isinstance(created, dict) and created.get("id"):
                    company_id = int(created.get("id"))
            except Exception:
                pass
        name_val = name.text().strip()
        if not name_val:
            raise ValueError("Name is required")
        if company_id == 0:
            raise ValueError("Company is required")
        if price.value() <= 0:
            raise ValueError("Price must be greater than 0")
        return {
            "name": name_val,
            "barcode": int(barcode.text()) if barcode.text().strip().isdigit() else None,
            "price": price.value(),
            "company_id": company_id,
        }
