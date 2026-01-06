from PyQt5 import QtWidgets, QtCore
from datetime import datetime


class TransactionsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Transactions")
        title.setObjectName("title")
        header.addWidget(title)
        header.addWidget(QtWidgets.QLabel("Date From"))
        self.start = QtWidgets.QDateEdit(); self.start.setCalendarPopup(True)
        self.start.setDate(QtCore.QDate.currentDate().addDays(-29))
        header.addWidget(self.start)
        header.addWidget(QtWidgets.QLabel("To"))
        self.end = QtWidgets.QDateEdit(); self.end.setCalendarPopup(True)
        self.end.setDate(QtCore.QDate.currentDate())
        header.addWidget(self.end)
        header.addWidget(QtWidgets.QLabel("User ID"))
        self.user_id = QtWidgets.QSpinBox(); self.user_id.setRange(0, 10**9)
        header.addWidget(self.user_id)
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "User", "Customer", "Total", "Paid", "Discount"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_delete.clicked.connect(self.delete_selected)

    def refresh(self):
        try:
            docs = self.api.transactions_list() or []
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        # filters
        try:
            start_dt = datetime.strptime(self.start.date().toString('yyyy-MM-dd'), '%Y-%m-%d')
            end_dt = datetime.strptime(self.end.date().toString('yyyy-MM-dd'), '%Y-%m-%d')
        except Exception:
            start_dt = end_dt = None
        uid = int(self.user_id.value())
        out = []
        for t in docs:
            try:
                ts = datetime.fromisoformat(t.get('date','').replace('Z',''))
            except Exception:
                ts = None
            if start_dt and ts and ts.date() < start_dt.date():
                continue
            if end_dt and ts and ts.date() > end_dt.date():
                continue
            if uid and int(t.get('user_id',0)) != uid:
                continue
            out.append(t)
        self.table.setRowCount(0)
        for t in out:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(t.get("date", "")))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(t.get("user_id", 0))))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(t.get("customer_id", 0))))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(f"{float(t.get('total', 0.0)):.2f}"))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(f"{float(t.get('paid', 0.0)):.2f}"))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(f"{float(t.get('discount', 0.0)):.2f}"))

    def delete_selected(self):
        r = self.table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a transaction row first")
            return
        # Load list and match by date+user+total (no id displayed)
        try:
            docs = self.api.transactions_list() or []
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e)); return
        date = self.table.item(r,0).text(); user_id = int(self.table.item(r,1).text() or 0); total = float(self.table.item(r,3).text())
        match = next((t for t in docs if t.get('date')==date and int(t.get('user_id',0))==user_id and float(t.get('total',0.0))==total), None)
        if not match:
            QtWidgets.QMessageBox.information(self, "Not Found", "Could not locate transaction to delete")
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this transaction?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            import requests
            requests.delete(self.api.base_url + f"/api/transactions/transaction/{int(match.get('id'))}")
            QtWidgets.QMessageBox.information(self, "Deleted", "Transaction deleted")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
