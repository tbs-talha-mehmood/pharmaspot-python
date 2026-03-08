from PyQt5 import QtWidgets, QtCore
from datetime import datetime
from .ui_common import (
    apply_header_layout,
    apply_page_layout,
    configure_table,
    polish_controls,
    set_danger,
    set_secondary,
)


class TransactionsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._user_name_by_id: dict[int, str] = {}
        self._customer_name_by_id: dict[int, str] = {}
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)

        header = QtWidgets.QHBoxLayout()
        apply_header_layout(header)

        header.addWidget(QtWidgets.QLabel("Date From"))
        self.start = QtWidgets.QDateEdit()
        self.start.setCalendarPopup(True)
        self.start.setDisplayFormat("dd-MM-yyyy")
        self.start.setMinimumWidth(130)
        self.start.setDate(QtCore.QDate.currentDate().addDays(-29))
        header.addWidget(self.start)

        header.addWidget(QtWidgets.QLabel("To"))
        self.end = QtWidgets.QDateEdit()
        self.end.setCalendarPopup(True)
        self.end.setDisplayFormat("dd-MM-yyyy")
        self.end.setMinimumWidth(130)
        self.end.setDate(QtCore.QDate.currentDate())
        header.addWidget(self.end)

        header.addWidget(QtWidgets.QLabel("User"))
        self.user_filter = QtWidgets.QComboBox()
        self.user_filter.setMinimumWidth(190)
        self.user_filter.addItem("All Users", 0)
        header.addWidget(self.user_filter)

        self.btn_reset = QtWidgets.QPushButton("Reset Filters")
        self.btn_payments = QtWidgets.QPushButton("Payments")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        set_secondary(self.btn_reset, self.btn_payments)
        set_danger(self.btn_delete)
        header.addWidget(self.btn_reset)
        header.addWidget(self.btn_payments)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Invoice #", "Date", "Time", "User", "Customer", "Total", "Paid", "Due", "Discount"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        for col in (5, 6, 7, 8):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
        self.table.setColumnWidth(1, 118)
        self.table.setColumnWidth(2, 92)
        self.table.setColumnWidth(5, 108)
        self.table.setColumnWidth(6, 108)
        self.table.setColumnWidth(7, 108)
        self.table.setColumnWidth(8, 108)
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

        self.start.dateChanged.connect(self._on_filter_changed)
        self.end.dateChanged.connect(self._on_filter_changed)
        self.user_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.btn_reset.clicked.connect(self._reset_filters)
        self.btn_payments.clicked.connect(self.show_payments)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.btn_payments.setVisible(True)
        self._page = 1
        self._pages = 1
        polish_controls(self)

    def _reset_filters(self):
        self.start.blockSignals(True)
        self.end.blockSignals(True)
        self.user_filter.blockSignals(True)
        self.start.setDate(QtCore.QDate.currentDate().addDays(-29))
        self.end.setDate(QtCore.QDate.currentDate())
        self.user_filter.setCurrentIndex(0)
        self.start.blockSignals(False)
        self.end.blockSignals(False)
        self.user_filter.blockSignals(False)
        self._page = 1
        self.refresh()

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

    def _rebuild_user_filter(self, docs):
        selected = 0
        try:
            selected = int(self.user_filter.currentData() or 0)
        except Exception:
            selected = 0
        users_from_docs = {}
        for t in docs or []:
            try:
                uid = int(t.get("user_id", 0) or 0)
            except Exception:
                uid = 0
            if uid <= 0:
                continue
            uname = self._user_display_name(
                uid,
                fallback=str(
                    t.get("user_name", "")
                    or t.get("username", "")
                    or t.get("user_fullname", "")
                    or t.get("fullname", "")
                ),
            )
            users_from_docs[uid] = uname
        for uid, uname in (self._user_name_by_id or {}).items():
            if int(uid) > 0 and uname:
                users_from_docs[int(uid)] = str(uname)
        self.user_filter.blockSignals(True)
        self.user_filter.clear()
        self.user_filter.addItem("All Users", 0)
        for uid, uname in sorted(users_from_docs.items(), key=lambda it: str(it[1]).lower()):
            self.user_filter.addItem(uname, int(uid))
        if selected:
            idx = self.user_filter.findData(int(selected))
            if idx >= 0:
                self.user_filter.setCurrentIndex(idx)
        self.user_filter.blockSignals(False)

    def _split_datetime(self, raw_value):
        dt = str(raw_value or "").strip()
        if not dt:
            return "", ""
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            return parsed.strftime("%d-%m-%Y"), parsed.strftime("%H:%M:%S")
        except Exception:
            normalized = dt.replace("T", " ")
            parts = normalized.split()
            date_txt = parts[0] if parts else normalized
            try:
                date_txt = datetime.strptime(date_txt, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                pass
            time_txt = ""
            if len(parts) > 1:
                time_txt = parts[1]
                if "." in time_txt:
                    time_txt = time_txt.split(".", 1)[0]
                if len(time_txt) > 8 and time_txt[8] in ("+", "-"):
                    time_txt = time_txt[:8]
            return date_txt, time_txt

    def _load_name_lookups(self, transactions_docs=None):
        user_map: dict[int, str] = dict(self._user_name_by_id or {})
        customer_map: dict[int, str] = dict(self._customer_name_by_id or {})

        # Prime lookups from transaction payload itself when names are present.
        for t in transactions_docs or []:
            try:
                uid = int(t.get("user_id", 0) or 0)
            except Exception:
                uid = 0
            uname = str(
                t.get("user_name", "")
                or t.get("username", "")
                or t.get("user_fullname", "")
                or t.get("fullname", "")
            ).strip()
            if uid > 0 and uname:
                user_map[uid] = uname

            try:
                cid = int(t.get("customer_id", 0) or 0)
            except Exception:
                cid = 0
            cname = str(t.get("customer_name", "") or t.get("customer", "")).strip()
            if cid > 0 and cname:
                customer_map[cid] = cname

        # Fill missing user names from users endpoint when available.
        try:
            users = self.api.users_all() or []
        except Exception:
            users = []
        for u in users:
            try:
                uid = int(u.get("id", 0) or 0)
            except Exception:
                uid = 0
            if uid <= 0:
                continue
            name = str(u.get("fullname", "") or u.get("username", "")).strip()
            if name:
                user_map[uid] = name

        # Fill missing customer names from customers endpoint when available.
        try:
            customers = self.api.customers(include_inactive=True) or []
        except Exception:
            customers = []
        for c in customers:
            try:
                cid = int(c.get("id", 0) or 0)
            except Exception:
                cid = 0
            if cid <= 0:
                continue
            name = str(c.get("name", "")).strip()
            if name:
                customer_map[cid] = name

        self._user_name_by_id = user_map
        self._customer_name_by_id = customer_map

    def _user_display_name(self, user_id, *, fallback: str = ""):
        try:
            uid = int(user_id or 0)
        except Exception:
            uid = 0
        txt = str(fallback or "").strip()
        if txt:
            return txt
        if uid > 0:
            return str(self._user_name_by_id.get(uid, "") or "Unknown User")
        return "Unknown User"

    def _customer_display_name(self, customer_id, *, fallback: str = ""):
        try:
            cid = int(customer_id or 0)
        except Exception:
            cid = 0
        txt = str(fallback or "").strip()
        if txt:
            return txt
        if cid > 0:
            return str(self._customer_name_by_id.get(cid, "") or "Walk-in")
        return "Walk-in"

    def refresh(self):
        try:
            uid = int(self.user_filter.currentData() or 0)
        except Exception:
            uid = 0
        try:
            start_txt = self.start.date().toString("yyyy-MM-dd")
            end_txt = self.end.date().toString("yyyy-MM-dd")
            data = self.api.transactions_page(
                start_date=start_txt,
                end_date=end_txt,
                user_id=uid,
                page=self._page,
                page_size=25,
            )
            docs = data.get("items", []) or []
            self._pages = int(data.get("pages", 1) or 1)
            self._page = max(1, min(int(data.get("page", self._page) or self._page), self._pages))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self._load_name_lookups(docs)
        self._rebuild_user_filter(docs)
        self.table.setRowCount(0)
        for t in docs:
            r = self.table.rowCount()
            self.table.insertRow(r)
            total = float(t.get("total", 0.0) or 0.0)
            paid = float(t.get("paid", 0.0) or 0.0)
            due = max(0.0, total - paid)
            date_txt, time_txt = self._split_datetime(t.get("date", ""))
            user_txt = self._user_display_name(
                t.get("user_id", 0),
                fallback=str(
                    t.get("user_name", "")
                    or t.get("username", "")
                    or t.get("user_fullname", "")
                    or t.get("fullname", "")
                ),
            )
            customer_txt = self._customer_display_name(
                t.get("customer_id", 0),
                fallback=str(t.get("customer_name", "") or t.get("customer", "")),
            )

            invoice_item = QtWidgets.QTableWidgetItem(str(t.get("id", 0)))
            date_item = QtWidgets.QTableWidgetItem(date_txt)
            time_item = QtWidgets.QTableWidgetItem(time_txt)
            user_item = QtWidgets.QTableWidgetItem(user_txt)
            customer_item = QtWidgets.QTableWidgetItem(customer_txt)
            total_item = QtWidgets.QTableWidgetItem(f"{total:.2f}")
            paid_item = QtWidgets.QTableWidgetItem(f"{paid:.2f}")
            due_item = QtWidgets.QTableWidgetItem(f"{due:.2f}")
            discount_item = QtWidgets.QTableWidgetItem(f"{float(t.get('discount', 0.0)):.2f}")

            date_item.setTextAlignment(QtCore.Qt.AlignCenter)
            time_item.setTextAlignment(QtCore.Qt.AlignCenter)
            user_item.setTextAlignment(QtCore.Qt.AlignCenter)
            total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            paid_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            due_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            discount_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

            self.table.setItem(r, 0, invoice_item)
            self.table.setItem(r, 1, date_item)
            self.table.setItem(r, 2, time_item)
            self.table.setItem(r, 3, user_item)
            self.table.setItem(r, 4, customer_item)
            self.table.setItem(r, 5, total_item)
            self.table.setItem(r, 6, paid_item)
            self.table.setItem(r, 7, due_item)
            self.table.setItem(r, 8, discount_item)
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)

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
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this transaction?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.api.transaction_delete(tid)
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

        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            max_dlg_w = int(geo.width() * 0.92)
            max_dlg_h = int(geo.height() * 0.90)
        else:
            max_dlg_w = 980
            max_dlg_h = 760
        row_h = 32
        chrome_h = 196
        col_widths = {
            0: 118,  # Date
            1: 92,   # Time
            2: 112,  # Amount
            3: 112,  # Paid Total
            4: 170,  # User
        }

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Payments for Invoice #{tid}")
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        table = QtWidgets.QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Date", "Time", "Amount", "Paid Total", "User", "Payment ID"])
        table.setColumnHidden(5, True)
        configure_table(table, stretch_last=False)
        table.verticalHeader().setDefaultSectionSize(row_h)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        hdr = table.horizontalHeader()
        for col, width in col_widths.items():
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
            table.setColumnWidth(col, width)
        v.addWidget(table)
        info = QtWidgets.QLabel("Edit a payment amount to correct payment history.")
        info.setObjectName("mutedLabel")
        v.addWidget(info)
        overflow_lbl = QtWidgets.QLabel("")
        overflow_lbl.setObjectName("mutedLabel")
        overflow_lbl.setVisible(False)
        v.addWidget(overflow_lbl)
        state = {"total_rows": 0}

        def _fit_dialog():
            table_frame = table.frameWidth() * 2 + 2
            table_w = sum(col_widths.values()) + table_frame
            table_h = table.frameWidth() * 2 + table.horizontalHeader().height() + (table.rowCount() * row_h) + 2
            table.setFixedSize(table_w, table_h)
            dlg.adjustSize()
            dlg.setFixedSize(min(max_dlg_w, dlg.sizeHint().width()), min(max_dlg_h, dlg.sizeHint().height()))

        def _load_rows():
            try:
                rows = self.api.transaction_payments(tid) or []
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return False
            if isinstance(rows, dict):
                QtWidgets.QMessageBox.information(self, "Payments", str(rows.get("detail", "Could not load payments")))
                return False
            rows = list(rows or [])
            rows.sort(key=lambda row: str(row.get("date", "") or ""), reverse=True)
            state["total_rows"] = len(rows)
            self._load_name_lookups()
            table.setRowCount(0)
            if not rows:
                overflow_lbl.setVisible(False)
                _fit_dialog()
                return True

            header_h = max(30, table.horizontalHeader().height())
            max_rows_fit = max(1, int((max_dlg_h - chrome_h - header_h) / max(1, row_h)))
            visible_rows = rows[:max_rows_fit]
            hidden_count = max(0, len(rows) - len(visible_rows))
            for row in visible_rows:
                rr = table.rowCount()
                table.insertRow(rr)
                dt = str(row.get("date", "") or "").strip()
                date_txt, time_txt = "", ""
                if dt:
                    try:
                        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                        date_txt = parsed.strftime("%d-%m-%Y")
                        time_txt = parsed.strftime("%H:%M:%S")
                    except Exception:
                        normalized = dt.replace("T", " ")
                        parts = normalized.split()
                        date_txt = parts[0] if parts else normalized
                        try:
                            date_txt = datetime.strptime(date_txt, "%Y-%m-%d").strftime("%d-%m-%Y")
                        except Exception:
                            pass
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
                user_txt = self._user_display_name(
                    uid,
                    fallback=str(
                        row.get("user_name", "")
                        or row.get("username", "")
                        or row.get("user_fullname", "")
                        or row.get("fullname", "")
                    ),
                )
                pid = int(row.get("id", 0) or 0)
                date_item = QtWidgets.QTableWidgetItem(date_txt)
                time_item = QtWidgets.QTableWidgetItem(time_txt)
                amount_item = QtWidgets.QTableWidgetItem(amt)
                paid_total_item = QtWidgets.QTableWidgetItem(f"{paid_total:.2f}")
                user_item = QtWidgets.QTableWidgetItem(user_txt)
                date_item.setTextAlignment(QtCore.Qt.AlignCenter)
                time_item.setTextAlignment(QtCore.Qt.AlignCenter)
                amount_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                paid_total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                table.setItem(rr, 0, date_item)
                table.setItem(rr, 1, time_item)
                table.setItem(rr, 2, amount_item)
                table.setItem(rr, 3, paid_total_item)
                table.setItem(rr, 4, user_item)
                table.setItem(rr, 5, QtWidgets.QTableWidgetItem(str(pid)))
            if hidden_count > 0:
                overflow_lbl.setText(
                    f"Showing latest {len(visible_rows)} of {len(rows)} payments to fit screen without scrolling."
                )
                overflow_lbl.setVisible(True)
            else:
                overflow_lbl.setVisible(False)
            _fit_dialog()
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
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        set_secondary(edit_btn, close_btn)
        row_btn = QtWidgets.QHBoxLayout()
        row_btn.addWidget(edit_btn)
        row_btn.addStretch(1)
        row_btn.addWidget(close_btn)
        v.addLayout(row_btn)
        polish_controls(dlg)
        _fit_dialog()
        dlg.exec_()
