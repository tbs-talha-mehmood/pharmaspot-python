from PyQt5 import QtWidgets


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
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_add = QtWidgets.QPushButton("Add Product")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_add)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Barcode", "Qty", "Price", "Category"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_add.clicked.connect(self.add_product_dialog)

    def refresh(self):
        try:
            items = self.api.products()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return

        self.table.setRowCount(0)
        for p in items:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(p.get("id"))))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(p.get("name", "")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(p.get("barcode", ""))))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(str(p.get("quantity", 0))))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(str(p.get("price", 0.0))))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(p.get("category", "")))

    def add_product_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add Product")
        form = QtWidgets.QFormLayout(d)
        name = QtWidgets.QLineEdit()
        barcode = QtWidgets.QLineEdit()
        qty = QtWidgets.QSpinBox()
        qty.setMaximum(10**9)
        price = QtWidgets.QDoubleSpinBox()
        price.setMaximum(10**9)
        price.setDecimals(2)
        category = QtWidgets.QLineEdit()
        form.addRow("Name", name)
        form.addRow("Barcode", barcode)
        form.addRow("Quantity", qty)
        form.addRow("Price", price)
        form.addRow("Category", category)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "name": name.text().strip(),
                "barcode": int(barcode.text()) if barcode.text().strip().isdigit() else None,
                "quantity": qty.value(),
                "price": price.value(),
                "category": category.text().strip(),
            }
            try:
                self.api.product_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
