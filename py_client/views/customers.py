from PyQt5 import QtWidgets


class CustomersView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Customers"))
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_add = QtWidgets.QPushButton("Add Customer")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_add)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Phone", "Email", "Address"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_add.clicked.connect(self.add_dialog)

    def refresh(self):
        try:
            items = self.api.customers()
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

    def add_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add Customer")
        form = QtWidgets.QFormLayout(d)
        name = QtWidgets.QLineEdit()
        phone = QtWidgets.QLineEdit()
        email = QtWidgets.QLineEdit()
        address = QtWidgets.QLineEdit()
        form.addRow("Name", name)
        form.addRow("Phone", phone)
        form.addRow("Email", email)
        form.addRow("Address", address)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "name": name.text().strip(),
                "phone": phone.text().strip(),
                "email": email.text().strip(),
                "address": address.text().strip(),
            }
            try:
                self.api.customer_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

