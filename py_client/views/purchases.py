from PyQt5 import QtWidgets


class PurchasesView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Purchases"))
        self.btn_new = QtWidgets.QPushButton("New Purchase")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_refresh = QtWidgets.QPushButton("Refresh History")
        header.addWidget(self.btn_new)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addWidget(self.btn_refresh)
        header.addStretch(1)
        layout.addLayout(header)

        # History table
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date", "Supplier", "Items", "Total"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.btn_new.clicked.connect(self.open_new_dialog)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.btn_delete.clicked.connect(self.delete_selected)

    def refresh(self):
        try:
            docs = self.api.purchases_list()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.table.setRowCount(0)
        for p in docs or []:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(p.get("date", "")))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(p.get("supplier_name", "")))
            items = p.get("items") or []
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(len(items))))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(f"{float(p.get('total', 0.0)):.2f}"))

    def open_new_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("New Purchase")
        v = QtWidgets.QVBoxLayout(d)

        form = QtWidgets.QFormLayout()
        supplier = QtWidgets.QComboBox()
        supplier.setEditable(True)
        try:
            supplier.clear()
            supplier.addItem("Select or type name", 0)
            for c in self.api.companies() or []:
                supplier.addItem(c.get("name", ""), int(c.get("id")))
        except Exception:
            pass
        form.addRow("Supplier", supplier)
        v.addLayout(form)

        items_table = QtWidgets.QTableWidget(0, 3)
        items_table.setHorizontalHeaderLabels(["Product ID", "Qty", "Price"])
        items_table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(items_table)

        btns_bar = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("Add Row")
        btn_rm = QtWidgets.QPushButton("Remove Row")
        btns_bar.addWidget(btn_add); btns_bar.addWidget(btn_rm); btns_bar.addStretch(1)
        v.addLayout(btns_bar)

        btnBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        v.addWidget(btnBox)

        def add_row():
            r = items_table.rowCount(); items_table.insertRow(r)
            items_table.setItem(r, 0, QtWidgets.QTableWidgetItem(""))
            items_table.setItem(r, 1, QtWidgets.QTableWidgetItem("1"))
            items_table.setItem(r, 2, QtWidgets.QTableWidgetItem("0.00"))

        def rm_row():
            r = items_table.currentRow()
            if r >= 0:
                items_table.removeRow(r)

        btn_add.clicked.connect(add_row)
        btn_rm.clicked.connect(rm_row)
        add_row()

        btnBox.accepted.connect(d.accept)
        btnBox.rejected.connect(d.reject)

        if d.exec_() == QtWidgets.QDialog.Accepted:
            # collect
            sid = supplier.currentData() or 0
            sname = supplier.currentText().strip()
            rows = []
            total = 0.0
            for r in range(items_table.rowCount()):
                try:
                    pid = int(items_table.item(r, 0).text())
                    qty = int(items_table.item(r, 1).text())
                    price = float(items_table.item(r, 2).text())
                    rows.append({"product_id": pid, "quantity": qty, "price": price})
                    total += qty * price
                except Exception:
                    pass
            payload = {
                "supplier_id": int(sid or 0),
                "supplier_name": sname,
                "total": total,
                "items": rows,
            }
            try:
                # save supplier if typed new
                if sid == 0 and sname:
                    self.api.company_upsert({"name": sname})
                self.api.purchase_new(payload)
                QtWidgets.QMessageBox.information(self, "Saved", "Purchase saved")
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _collect_dialog_payload(self, d, supplier, items_table):
        sid = supplier.currentData() or 0
        sname = supplier.currentText().strip()
        rows = []
        total = 0.0
        for r in range(items_table.rowCount()):
            try:
                pid = int(items_table.item(r, 0).text())
                qty = int(items_table.item(r, 1).text())
                price = float(items_table.item(r, 2).text())
                rows.append({"product_id": pid, "quantity": qty, "price": price})
                total += qty * price
            except Exception:
                pass
        return sid, sname, rows, total

    def _build_purchase_dialog(self, title: str, existing: dict | None = None):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(title)
        v = QtWidgets.QVBoxLayout(d)
        form = QtWidgets.QFormLayout()
        supplier = QtWidgets.QComboBox(); supplier.setEditable(True)
        try:
            supplier.clear(); supplier.addItem("Select or type name", 0)
            for c in self.api.companies() or []:
                supplier.addItem(c.get("name", ""), int(c.get("id")))
        except Exception:
            pass
        if existing and existing.get('supplier_name'):
            supplier.setCurrentText(existing.get('supplier_name'))
        form.addRow("Supplier", supplier)
        v.addLayout(form)
        items_table = QtWidgets.QTableWidget(0, 3)
        items_table.setHorizontalHeaderLabels(["Product ID", "Qty", "Price"])
        items_table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(items_table)
        btns_bar = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("Add Row")
        btn_rm = QtWidgets.QPushButton("Remove Row")
        btns_bar.addWidget(btn_add); btns_bar.addWidget(btn_rm); btns_bar.addStretch(1)
        v.addLayout(btns_bar)
        btnBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        v.addWidget(btnBox)
        def add_row():
            r = items_table.rowCount(); items_table.insertRow(r)
            items_table.setItem(r, 0, QtWidgets.QTableWidgetItem(""))
            items_table.setItem(r, 1, QtWidgets.QTableWidgetItem("1"))
            items_table.setItem(r, 2, QtWidgets.QTableWidgetItem("0.00"))
        def rm_row():
            r = items_table.currentRow()
            if r >= 0:
                items_table.removeRow(r)
        btn_add.clicked.connect(add_row); btn_rm.clicked.connect(rm_row)
        if existing:
            for it in existing.get('items', []) or []:
                add_row()
                r = items_table.rowCount()-1
                items_table.item(r,0).setText(str(it.get('product_id', '')))
                items_table.item(r,1).setText(str(it.get('quantity', '1')))
                items_table.item(r,2).setText(f"{float(it.get('price', 0.0)):.2f}")
        else:
            add_row()
        btnBox.accepted.connect(d.accept); btnBox.rejected.connect(d.reject)
        return d, supplier, items_table

    def edit_selected(self):
        r = self.table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a purchase row first")
            return
        # there is no id column in table; reload list and map by date+total+supplier (best effort)
        docs = self.api.purchases_list() or []
        date = self.table.item(r,0).text(); supplier = self.table.item(r,1).text(); total = float(self.table.item(r,3).text())
        match = next((p for p in docs if p.get('date')==date and p.get('supplier_name')==supplier and float(p.get('total',0.0))==total), None)
        if not match:
            QtWidgets.QMessageBox.information(self, "Not Found", "Could not locate purchase to edit")
            return
        d, supplier_cb, items_table = self._build_purchase_dialog("Edit Purchase", match)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            sid, sname, rows, total = self._collect_dialog_payload(d, supplier_cb, items_table)
            payload = {"supplier_id": int(sid or 0), "supplier_name": sname, "total": total, "items": rows}
            try:
                self.api.post_json(f"/api/purchases/purchase/{int(match.get('id'))}", payload)
                QtWidgets.QMessageBox.information(self, "Saved", "Purchase updated")
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def delete_selected(self):
        r = self.table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a purchase row first")
            return
        docs = self.api.purchases_list() or []
        date = self.table.item(r,0).text(); supplier = self.table.item(r,1).text(); total = float(self.table.item(r,3).text())
        match = next((p for p in docs if p.get('date')==date and p.get('supplier_name')==supplier and float(p.get('total',0.0))==total), None)
        if not match:
            QtWidgets.QMessageBox.information(self, "Not Found", "Could not locate purchase to delete")
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this purchase?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            import requests
            requests.delete(self.api.base_url + f"/api/purchases/purchase/{int(match.get('id'))}")
            QtWidgets.QMessageBox.information(self, "Deleted", "Purchase deleted")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
