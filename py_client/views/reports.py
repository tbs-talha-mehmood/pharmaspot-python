from datetime import datetime

from PyQt5 import QtCore, QtWidgets

from .ui_common import (
    apply_header_layout,
    apply_page_layout,
    configure_table,
    polish_controls,
    set_secondary,
)


class ReportsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._user_name_by_id: dict[int, str] = {}
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)

        filters = QtWidgets.QHBoxLayout()
        apply_header_layout(filters)

        filters.addWidget(QtWidgets.QLabel("Date From"))
        self.start = QtWidgets.QDateEdit()
        self.start.setCalendarPopup(True)
        self.start.setDisplayFormat("dd-MM-yyyy")
        self.start.setDate(QtCore.QDate.currentDate().addDays(-29))
        self.start.setMinimumWidth(130)
        filters.addWidget(self.start)

        filters.addWidget(QtWidgets.QLabel("To"))
        self.end = QtWidgets.QDateEdit()
        self.end.setCalendarPopup(True)
        self.end.setDisplayFormat("dd-MM-yyyy")
        self.end.setDate(QtCore.QDate.currentDate())
        self.end.setMinimumWidth(130)
        filters.addWidget(self.end)

        filters.addWidget(QtWidgets.QLabel("User"))
        self.user_filter = QtWidgets.QComboBox()
        self.user_filter.setMinimumWidth(190)
        self.user_filter.addItem("All Users", 0)
        filters.addWidget(self.user_filter)

        self.btn_reset = QtWidgets.QPushButton("Reset Filters")
        set_secondary(self.btn_reset)
        filters.addWidget(self.btn_reset)
        filters.addStretch(1)
        layout.addLayout(filters)

        metrics = QtWidgets.QHBoxLayout()
        apply_header_layout(metrics)
        tx_card, self.tx_count_label = self._metric_card("Transactions", "0")
        gross_card, self.gross_label = self._metric_card("Gross Sales", "0.00")
        paid_card, self.paid_label = self._metric_card("Paid", "0.00")
        due_card, self.due_label = self._metric_card("Due", "0.00")
        metrics.addWidget(tx_card)
        metrics.addWidget(gross_card)
        metrics.addWidget(paid_card)
        metrics.addWidget(due_card)
        layout.addLayout(metrics)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Invoices", "Gross", "Paid", "Due", "Discount"])
        configure_table(self.table, stretch_last=False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        for col in (2, 3, 4, 5):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        self.table.setColumnWidth(0, 118)
        self.table.setColumnWidth(1, 92)
        layout.addWidget(self.table, 1)

        self.start.dateChanged.connect(self.refresh)
        self.end.dateChanged.connect(self.refresh)
        self.user_filter.currentIndexChanged.connect(self.refresh)
        self.btn_reset.clicked.connect(self._reset_filters)
        polish_controls(self)

    def _metric_card(self, title: str, value: str):
        card = QtWidgets.QGroupBox(title)
        card.setObjectName("totalsCard")
        row = QtWidgets.QVBoxLayout(card)
        row.setContentsMargins(10, 8, 10, 10)
        row.setSpacing(2)
        label = QtWidgets.QLabel(value)
        label.setObjectName("moneyStrong")
        row.addWidget(label)
        return card, label

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
        self.refresh()

    def _parse_datetime(self, raw_value):
        dt = str(raw_value or "").strip()
        if not dt:
            return None
        try:
            return datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            try:
                return datetime.strptime(dt.replace("T", " ").split(".", 1)[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

    def _load_user_lookup(self, docs):
        user_map: dict[int, str] = {}
        for t in docs or []:
            try:
                uid = int(t.get("user_id", 0) or 0)
            except Exception:
                uid = 0
            if uid <= 0:
                continue
            name = str(
                t.get("user_name", "")
                or t.get("username", "")
                or t.get("user_fullname", "")
                or t.get("fullname", "")
            ).strip()
            if name:
                user_map[uid] = name
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
        self._user_name_by_id = user_map

    def _rebuild_user_filter(self):
        selected = 0
        try:
            selected = int(self.user_filter.currentData() or 0)
        except Exception:
            selected = 0
        self.user_filter.blockSignals(True)
        self.user_filter.clear()
        self.user_filter.addItem("All Users", 0)
        for uid, uname in sorted(self._user_name_by_id.items(), key=lambda item: str(item[1]).lower()):
            self.user_filter.addItem(str(uname), int(uid))
        if selected:
            idx = self.user_filter.findData(int(selected))
            if idx >= 0:
                self.user_filter.setCurrentIndex(idx)
        self.user_filter.blockSignals(False)

    def refresh(self):
        try:
            docs = self.api.transactions_list() or []
        except Exception:
            docs = []

        self._load_user_lookup(docs)
        self._rebuild_user_filter()

        try:
            start_dt = self.start.date().toPyDate()
            end_dt = self.end.date().toPyDate()
        except Exception:
            start_dt = end_dt = None
        try:
            uid = int(self.user_filter.currentData() or 0)
        except Exception:
            uid = 0

        grouped: dict = {}
        tx_count = 0
        gross_total = 0.0
        paid_total = 0.0
        due_total = 0.0

        for t in docs:
            try:
                tx_uid = int(t.get("user_id", 0) or 0)
            except Exception:
                tx_uid = 0
            if uid and tx_uid != uid:
                continue

            ts = self._parse_datetime(t.get("date", ""))
            if ts is None:
                continue
            day = ts.date()
            if start_dt and day < start_dt:
                continue
            if end_dt and day > end_dt:
                continue

            try:
                gross = float(t.get("total", 0.0) or 0.0)
            except Exception:
                gross = 0.0
            try:
                paid = float(t.get("paid", 0.0) or 0.0)
            except Exception:
                paid = 0.0
            try:
                discount = float(t.get("discount", 0.0) or 0.0)
            except Exception:
                discount = 0.0

            due = max(0.0, gross - paid)
            bucket = grouped.setdefault(
                day,
                {"count": 0, "gross": 0.0, "paid": 0.0, "due": 0.0, "discount": 0.0},
            )
            bucket["count"] += 1
            bucket["gross"] += gross
            bucket["paid"] += paid
            bucket["due"] += due
            bucket["discount"] += discount

            tx_count += 1
            gross_total += gross
            paid_total += paid
            due_total += due

        self.tx_count_label.setText(str(tx_count))
        self.gross_label.setText(f"{gross_total:.2f}")
        self.paid_label.setText(f"{paid_total:.2f}")
        self.due_label.setText(f"{due_total:.2f}")

        rows = sorted(grouped.items(), key=lambda item: item[0], reverse=True)
        self.table.setRowCount(0)
        for day, data in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            date_item = QtWidgets.QTableWidgetItem(day.strftime("%d-%m-%Y"))
            count_item = QtWidgets.QTableWidgetItem(str(int(data["count"])))
            gross_item = QtWidgets.QTableWidgetItem(f"{float(data['gross']):.2f}")
            paid_item = QtWidgets.QTableWidgetItem(f"{float(data['paid']):.2f}")
            due_item = QtWidgets.QTableWidgetItem(f"{float(data['due']):.2f}")
            discount_item = QtWidgets.QTableWidgetItem(f"{float(data['discount']):.2f}")

            date_item.setTextAlignment(QtCore.Qt.AlignCenter)
            count_item.setTextAlignment(QtCore.Qt.AlignCenter)
            for itm in (gross_item, paid_item, due_item, discount_item):
                itm.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

            self.table.setItem(r, 0, date_item)
            self.table.setItem(r, 1, count_item)
            self.table.setItem(r, 2, gross_item)
            self.table.setItem(r, 3, paid_item)
            self.table.setItem(r, 4, due_item)
            self.table.setItem(r, 5, discount_item)
