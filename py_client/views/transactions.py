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
        self.btn_payments = QtWidgets.QPushButton("Payments")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_payments)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Invoice #", "Date", "User", "Customer", "Total", "Paid", "Due", "Discount"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_payments.clicked.connect(self.show_payments)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_payments.setVisible(True)

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
            total = float(t.get("total", 0.0) or 0.0)
            paid = float(t.get("paid", 0.0) or 0.0)
            due = max(0.0, total - paid)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(t.get("id", 0))))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(t.get("date", "")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(t.get("user_id", 0))))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(str(t.get("customer_id", 0))))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(f"{total:.2f}"))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(f"{paid:.2f}"))
            self.table.setItem(r, 6, QtWidgets.QTableWidgetItem(f"{due:.2f}"))
            self.table.setItem(r, 7, QtWidgets.QTableWidgetItem(f"{float(t.get('discount', 0.0)):.2f}"))

    def delete_selected(self):
        r = self.table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a transaction row first")
            return
        tid_item = self.table.item(r, 0)
        if not tid_item:
            QtWidgets.QMessageBox.information(self, "Select", "Invalid transaction row")
            return
        try:
            tid = int(tid_item.text() or 0)
        except Exception:
            tid = 0
        if tid <= 0:
            QtWidgets.QMessageBox.information(self, "Select", "Invalid invoice number")
            return
        try:
            docs = self.api.transactions_list() or []
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e)); return
        match = next((t for t in docs if int(t.get('id', 0) or 0) == tid), None)
        if not match:
            QtWidgets.QMessageBox.information(self, "Not Found", "Could not locate transaction to delete")
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this transaction?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            import requests
            requests.delete(self.api.base_url + f"/api/transactions/transaction/{tid}")
            QtWidgets.QMessageBox.information(self, "Deleted", "Transaction deleted")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def show_payments(self):
        r = self.table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select an invoice row first")
            return
        tid_item = self.table.item(r, 0)
        if not tid_item:
            QtWidgets.QMessageBox.information(self, "Select", "Invalid invoice row")
            return
        try:
            tid = int(tid_item.text() or 0)
        except Exception:
            tid = 0
        if tid <= 0:
            QtWidgets.QMessageBox.information(self, "Select", "Invalid invoice number")
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Payments for Invoice #{tid}")
        v = QtWidgets.QVBoxLayout(dlg)
        table = QtWidgets.QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Date", "Time", "Amount", "Paid Total", "User ID", "Payment ID"])
        table.setColumnHidden(5, True)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        v.addWidget(table)
        info = QtWidgets.QLabel("Edit a payment amount to correct payment history.")
        v.addWidget(info)

        def _load_rows():
            try:
                rows = self.api.transaction_payments(tid) or []
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return False
            if isinstance(rows, dict):
                QtWidgets.QMessageBox.information(self, "Payments", str(rows.get("detail", "Could not load payments")))
                return False
            table.setRowCount(0)
            for row in rows:
                rr = table.rowCount()
                table.insertRow(rr)
                dt = str(row.get("date", "") or "").strip()
                date_txt, time_txt = "", ""
                if dt:
                    try:
                        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                        date_txt = parsed.strftime("%Y-%m-%d")
                        time_txt = parsed.strftime("%H:%M:%S")
                    except Exception:
                        normalized = dt.replace("T", " ")
                        parts = normalized.split()
                        date_txt = parts[0] if parts else normalized
                        if len(parts) > 1:
                            time_txt = parts[1]
                            if "." in time_txt:
                                time_txt = time_txt.split(".", 1)[0]
                            if len(time_txt) > 8 and time_txt[8] in ("+", "-"):
                                time_txt = time_txt[:8]
                try:
                    amt_f = float(row.get("amount", 0.0) or 0.0)
                except Exception:
                    amt_f = 0.0
                amt = f"+{amt_f:.2f}" if amt_f >= 0 else f"{amt_f:.2f}"
                try:
                    paid_total = float(row.get("paid_total", 0.0) or 0.0)
                except Exception:
                    paid_total = 0.0
                uid = int(row.get("user_id", 0) or 0)
                pid = int(row.get("id", 0) or 0)
                table.setItem(rr, 0, QtWidgets.QTableWidgetItem(date_txt))
                table.setItem(rr, 1, QtWidgets.QTableWidgetItem(time_txt))
                table.setItem(rr, 2, QtWidgets.QTableWidgetItem(amt))
                table.setItem(rr, 3, QtWidgets.QTableWidgetItem(f"{paid_total:.2f}"))
                table.setItem(rr, 4, QtWidgets.QTableWidgetItem(str(uid)))
                table.setItem(rr, 5, QtWidgets.QTableWidgetItem(str(pid)))
            table.resizeRowsToContents()
            return True

        def _edit_selected():
            rr = table.currentRow()
            if rr < 0:
                QtWidgets.QMessageBox.information(self, "Payments", "Select a payment row first.")
                return
            id_item = table.item(rr, 5)
            amt_item = table.item(rr, 2)
            if not id_item or not amt_item:
                QtWidgets.QMessageBox.information(self, "Payments", "Invalid payment row.")
                return
            try:
                payment_id = int(id_item.text() or 0)
            except Exception:
                payment_id = 0
            if payment_id <= 0:
                QtWidgets.QMessageBox.information(self, "Payments", "Invalid payment ID.")
                return
            try:
                current_amount = float((amt_item.text() or "0").replace("+", ""))
            except Exception:
                current_amount = 0.0
            new_amount, ok = QtWidgets.QInputDialog.getDouble(
                dlg,
                "Edit Payment",
                "Payment amount:",
                value=current_amount,
                min=0.0,
                max=10**12,
                decimals=2,
            )
            if not ok:
                return
            try:
                resp = self.api.transaction_payment_update(tid, payment_id, float(new_amount))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                QtWidgets.QMessageBox.information(self, "Payments", str(resp.get("detail")))
                return
            _load_rows()
            self.refresh()

        if not _load_rows():
            return
        if table.rowCount() <= 0:
            QtWidgets.QMessageBox.information(self, "Payments", f"No payment entries for invoice #{tid}.")
            return
        edit_btn = QtWidgets.QPushButton("Edit Selected")
        edit_btn.clicked.connect(_edit_selected)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(_load_rows)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        row_btn = QtWidgets.QHBoxLayout()
        row_btn.addWidget(edit_btn)
        row_btn.addWidget(refresh_btn)
        row_btn.addStretch(1)
        row_btn.addWidget(close_btn)
        v.addLayout(row_btn)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            dlg.resize(int(geo.width() * 0.92), int(geo.height() * 0.9))
        dlg.exec_()
