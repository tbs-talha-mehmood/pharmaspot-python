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
        self._user_id: int = 0
        self._is_admin: bool = False
        self._can_edit_invoice: bool = False
        self._can_delete_payment: bool = False
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
        self.btn_delete = QtWidgets.QPushButton("Delete")
        set_secondary(self.btn_reset)
        set_danger(self.btn_delete)
        header.addWidget(self.btn_reset)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 13)
        self.table.setHorizontalHeaderLabels(
            [
                "Invoice #",
                "Date",
                "User",
                "Customer",
                "Total",
                "Paid",
                "Due",
                "Discount",
                "COGS",
                "Profit",
                "Cash Profit",
                "Realized",
                "Provisional",
            ]
        )
        configure_table(self.table, stretch_last=False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)          # Date
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # User
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)        # Customer
        for col in (4, 5, 6, 7, 8, 9, 10, 11, 12):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
        self.table.setColumnWidth(1, 118)
        self.table.setColumnWidth(4, 108)
        self.table.setColumnWidth(5, 108)
        self.table.setColumnWidth(6, 108)
        self.table.setColumnWidth(7, 108)
        self.table.setColumnWidth(8, 108)
        self.table.setColumnWidth(9, 108)
        self.table.setColumnWidth(10, 108)
        self.table.setColumnWidth(11, 108)
        self.table.setColumnWidth(12, 108)
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
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self._page = 1
        self._pages = 1
        polish_controls(self)

    def set_user(self, user: dict):
        u = user or {}
        try:
            self._user_id = int(u.get("id", 0) or 0)
        except Exception:
            self._user_id = 0
        uname = str(u.get("username", "") or "").strip().lower()
        self._is_admin = bool(self._user_id == 1 or uname == "admin")
        self._can_edit_invoice = bool(u.get("perm_edit_invoice", False) or self._is_admin)
        self._can_delete_payment = bool(u.get("perm_delete_payment", False) or self._is_admin)
        self.btn_delete.setEnabled(self._can_edit_invoice)

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
            cogs = float(t.get("cogs", 0.0) or 0.0)
            profit = float(t.get("profit", 0.0) or 0.0)
            cash_profit = profit * (paid / total) if total > 1e-9 else 0.0
            realized = float(t.get("realized", 0.0) or 0.0)
            provisional = float(t.get("provisional", 0.0) or 0.0)
            date_txt, _ = self._split_datetime(t.get("date", ""))
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
            user_item = QtWidgets.QTableWidgetItem(user_txt)
            customer_item = QtWidgets.QTableWidgetItem(customer_txt)
            total_item = QtWidgets.QTableWidgetItem(f"{total:.2f}")
            paid_item = QtWidgets.QTableWidgetItem(f"{paid:.2f}")
            due_item = QtWidgets.QTableWidgetItem(f"{due:.2f}")
            discount_item = QtWidgets.QTableWidgetItem(f"{float(t.get('discount', 0.0)):.2f}")
            cogs_item = QtWidgets.QTableWidgetItem(f"{cogs:.2f}")
            profit_item = QtWidgets.QTableWidgetItem(f"{profit:.2f}")
            cash_profit_item = QtWidgets.QTableWidgetItem(f"{cash_profit:.2f}")
            realized_item = QtWidgets.QTableWidgetItem(f"{realized:.2f}")
            provisional_item = QtWidgets.QTableWidgetItem(f"{provisional:.2f}")

            date_item.setTextAlignment(QtCore.Qt.AlignCenter)
            user_item.setTextAlignment(QtCore.Qt.AlignCenter)
            total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            paid_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            due_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            discount_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            cogs_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            profit_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            cash_profit_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            realized_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            provisional_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

            self.table.setItem(r, 0, invoice_item)
            self.table.setItem(r, 1, date_item)
            self.table.setItem(r, 2, user_item)
            self.table.setItem(r, 3, customer_item)
            self.table.setItem(r, 4, total_item)
            self.table.setItem(r, 5, paid_item)
            self.table.setItem(r, 6, due_item)
            self.table.setItem(r, 7, discount_item)
            self.table.setItem(r, 8, cogs_item)
            self.table.setItem(r, 9, profit_item)
            self.table.setItem(r, 10, cash_profit_item)
            self.table.setItem(r, 11, realized_item)
            self.table.setItem(r, 12, provisional_item)
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)

    def delete_selected(self):
        if not self._can_edit_invoice:
            QtWidgets.QMessageBox.information(
                self,
                "Permission",
                "You do not have permission to delete invoices.",
            )
            return
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
            self.api.transaction_delete(tid, user_id=int(self._user_id or 0))
            QtWidgets.QMessageBox.information(self, "Deleted", "Transaction deleted")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
