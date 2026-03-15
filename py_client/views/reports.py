from collections import defaultdict, deque
from datetime import datetime

from PyQt5 import QtCore, QtWidgets, QtGui

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
        self.btn_reconcile = QtWidgets.QPushButton("Profit Reconciliation")
        set_secondary(self.btn_reset)
        set_secondary(self.btn_reconcile)
        filters.addWidget(self.btn_reset)
        filters.addWidget(self.btn_reconcile)
        filters.addStretch(1)
        layout.addLayout(filters)

        metrics = QtWidgets.QHBoxLayout()
        apply_header_layout(metrics)
        tx_card, self.tx_count_label = self._metric_card("Transactions", "0")
        gross_card, self.gross_label = self._metric_card("Sales (Net)", "0.00")
        paid_card, self.paid_label = self._metric_card("Cash Received", "0.00")
        due_card, self.due_label = self._metric_card("Due", "0.00")
        profit_card, self.profit_label = self._metric_card("Profit (Accrual)", "0.00")
        realized_card, self.realized_profit_label = self._metric_card("Profit (Cash)", "0.00")
        metrics.addWidget(tx_card)
        metrics.addWidget(gross_card)
        metrics.addWidget(paid_card)
        metrics.addWidget(due_card)
        metrics.addWidget(profit_card)
        metrics.addWidget(realized_card)
        layout.addLayout(metrics)

        self.provisional_note = QtWidgets.QLabel("")
        self.provisional_note.setObjectName("mutedLabel")
        layout.addWidget(self.provisional_note)

        self.table = QtWidgets.QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Invoices", "Sales", "Received", "Due", "COGS", "Profit", "Cash Profit", "Provisional"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        for col in (2, 3, 4, 5, 6, 7, 8):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        self.table.setColumnWidth(0, 118)
        self.table.setColumnWidth(1, 92)
        layout.addWidget(self.table, 1)

        self.start.dateChanged.connect(self.refresh)
        self.end.dateChanged.connect(self.refresh)
        self.user_filter.currentIndexChanged.connect(self.refresh)
        self.btn_reset.clicked.connect(self._reset_filters)
        self.btn_reconcile.clicked.connect(self._open_profit_reconciliation)
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

    def _open_profit_reconciliation(self):
        start_txt = self.start.date().toString("yyyy-MM-dd")
        end_txt = self.end.date().toString("yyyy-MM-dd")
        try:
            uid = int(self.user_filter.currentData() or 0)
        except Exception:
            uid = 0

        try:
            data = self.api.profit_reconciliation(start_date=start_txt, end_date=end_txt, user_id=uid) or {}
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        if isinstance(data, dict) and str(data.get("detail", "")).strip():
            QtWidgets.QMessageBox.information(self, "Profit Reconciliation", str(data.get("detail", "")).strip())
            return

        summary = dict(data.get("summary") or {})
        items = list(data.get("items") or [])
        start_date = str(data.get("start_date", start_txt) or start_txt)
        end_date = str(data.get("end_date", end_txt) or end_txt)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Profit Reconciliation")
        layout = QtWidgets.QVBoxLayout(dlg)
        apply_page_layout(layout)

        head = QtWidgets.QHBoxLayout()
        apply_header_layout(head)
        head.addWidget(QtWidgets.QLabel(f"Period: {start_date} to {end_date}"))
        if uid > 0:
            uname = self._user_name_by_id.get(int(uid), f"User {int(uid)}")
            head.addWidget(QtWidgets.QLabel(f"User: {uname}"))
        head.addStretch(1)
        layout.addLayout(head)

        sums = QtWidgets.QHBoxLayout()
        apply_header_layout(sums)
        s1 = QtWidgets.QLabel(
            f"Expected COGS: {self._to_float(summary.get('expected_cogs', 0.0), 0.0):.2f}"
        )
        s2 = QtWidgets.QLabel(
            f"Actual COGS: {self._to_float(summary.get('actual_cogs', 0.0), 0.0):.2f}"
        )
        s3 = QtWidgets.QLabel(
            f"Difference: {self._to_float(summary.get('difference', 0.0), 0.0):.2f}"
        )
        s4 = QtWidgets.QLabel(f"Profit: {self._to_float(summary.get('profit', 0.0), 0.0):.2f}")
        s5 = QtWidgets.QLabel(f"Mismatches: {self._to_int(summary.get('mismatch_count', 0), 0)}")
        for lbl in (s1, s2, s3, s4, s5):
            lbl.setObjectName("mutedLabel")
            sums.addWidget(lbl)
        sums.addStretch(1)
        layout.addLayout(sums)

        table = QtWidgets.QTableWidget(0, 14)
        table.setHorizontalHeaderLabels(
            [
                "Product",
                "Open Qty",
                "Open Value",
                "Purch Qty",
                "Purch Value",
                "Close Qty",
                "Close Value",
                "Expected COGS",
                "Actual COGS",
                "Difference",
                "Sales",
                "Profit",
                "Provisional",
                "Mismatch",
            ]
        )
        configure_table(table, stretch_last=False)
        table.verticalHeader().setDefaultSectionSize(34)
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in range(1, 14):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(table, 1)

        rows = sorted(items, key=lambda it: (not bool(it.get("mismatch", False)), str(it.get("product_name", "")).lower()))
        table.setRowCount(0)
        for row in rows:
            r = table.rowCount()
            table.insertRow(r)

            product_item = QtWidgets.QTableWidgetItem(str(row.get("product_name", "") or ""))
            open_qty_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('opening_qty', 0.0), 0.0):.2f}")
            open_val_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('opening_value', 0.0), 0.0):.2f}")
            purch_qty_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('purchases_qty', 0.0), 0.0):.2f}")
            purch_val_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('purchases_value', 0.0), 0.0):.2f}")
            close_qty_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('closing_qty', 0.0), 0.0):.2f}")
            close_val_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('closing_value', 0.0), 0.0):.2f}")
            exp_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('expected_cogs', 0.0), 0.0):.2f}")
            act_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('actual_cogs', 0.0), 0.0):.2f}")
            diff_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('difference', 0.0), 0.0):.2f}")
            sales_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('sales_value', 0.0), 0.0):.2f}")
            profit_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('profit', 0.0), 0.0):.2f}")
            prov_item = QtWidgets.QTableWidgetItem(f"{self._to_float(row.get('provisional_open_cost', 0.0), 0.0):.2f}")
            mismatch = bool(row.get("mismatch", False))
            mismatch_item = QtWidgets.QTableWidgetItem("Yes" if mismatch else "No")

            product_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            for itm in (
                open_qty_item,
                open_val_item,
                purch_qty_item,
                purch_val_item,
                close_qty_item,
                close_val_item,
                exp_item,
                act_item,
                diff_item,
                sales_item,
                profit_item,
                prov_item,
            ):
                itm.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            mismatch_item.setTextAlignment(QtCore.Qt.AlignCenter)

            if mismatch:
                for itm in (diff_item, mismatch_item):
                    itm.setForeground(QtGui.QBrush(QtGui.QColor("#F87171")))

            table.setItem(r, 0, product_item)
            table.setItem(r, 1, open_qty_item)
            table.setItem(r, 2, open_val_item)
            table.setItem(r, 3, purch_qty_item)
            table.setItem(r, 4, purch_val_item)
            table.setItem(r, 5, close_qty_item)
            table.setItem(r, 6, close_val_item)
            table.setItem(r, 7, exp_item)
            table.setItem(r, 8, act_item)
            table.setItem(r, 9, diff_item)
            table.setItem(r, 10, sales_item)
            table.setItem(r, 11, profit_item)
            table.setItem(r, 12, prov_item)
            table.setItem(r, 13, mismatch_item)

        btn_row = QtWidgets.QHBoxLayout()
        apply_header_layout(btn_row)
        btn_close = QtWidgets.QPushButton("Close")
        set_secondary(btn_close)
        btn_close.clicked.connect(dlg.accept)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        polish_controls(dlg)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            dlg.resize(min(1450, max(1000, geo.width() - 80)), min(860, max(620, geo.height() - 80)))
        else:
            dlg.resize(1280, 760)
        dlg.exec_()

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

    def _to_int(self, value, default: int = 0) -> int:
        try:
            return int(value if value is not None else default)
        except Exception:
            return int(default)

    def _to_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value if value is not None else default)
        except Exception:
            return float(default)

    def _sale_unit_price(self, item: dict) -> float:
        unit = item.get("unit_price")
        if unit is not None:
            return max(0.0, self._to_float(unit, 0.0))
        trade = item.get("trade_price")
        if trade is not None:
            extra_pct = max(0.0, self._to_float(item.get("extra_discount_pct", 0.0), 0.0))
            return max(0.0, self._to_float(trade, 0.0) * (1.0 - (extra_pct / 100.0)))
        retail = self._to_float(item.get("retail_price", 0.0), 0.0)
        disc_pct = max(0.0, self._to_float(item.get("discount_pct", 0.0), 0.0))
        extra_pct = max(0.0, self._to_float(item.get("extra_discount_pct", 0.0), 0.0))
        trade_calc = retail * (1.0 - (disc_pct / 100.0))
        return max(0.0, trade_calc * (1.0 - (extra_pct / 100.0)))

    def _purchase_unit_cost(self, item: dict) -> float:
        price = item.get("price")
        if price is not None:
            return max(0.0, self._to_float(price, 0.0))
        trade = item.get("trade_price")
        if trade is not None:
            return max(0.0, self._to_float(trade, 0.0))
        retail = self._to_float(item.get("retail_price", 0.0), 0.0)
        disc_pct = max(0.0, self._to_float(item.get("discount_pct", 0.0), 0.0))
        extra_pct = max(0.0, self._to_float(item.get("extra_discount_pct", 0.0), 0.0))
        trade_calc = retail * (1.0 - (disc_pct / 100.0))
        return max(0.0, trade_calc * (1.0 - (extra_pct / 100.0)))

    def _product_cost_hint(self, product: dict) -> float:
        trade = max(0.0, self._to_float(product.get("trade_price", 0.0), 0.0))
        if trade > 1e-9:
            return trade
        retail = max(0.0, self._to_float(product.get("price", 0.0), 0.0))
        raw_disc = product.get("discount_pct", product.get("purchase_discount", 0.0))
        disc = max(0.0, self._to_float(raw_disc, 0.0))
        if retail > 1e-9:
            return max(0.0, retail * (1.0 - (disc / 100.0)))
        return 0.0

    def _build_invoice_profit_map(self, docs, purchases, product_cost_hint_by_id: dict[int, float] | None = None):
        product_cost_hint_by_id = dict(product_cost_hint_by_id or {})
        invoices: dict[int, dict] = {}
        events: list[tuple] = []

        for t in docs or []:
            tid = self._to_int(t.get("id", 0), 0)
            if tid <= 0:
                continue
            ts = self._parse_datetime(t.get("date", ""))
            tx_uid = self._to_int(t.get("user_id", 0), 0)
            total_gross = max(0.0, self._to_float(t.get("total", 0.0), 0.0))
            paid = max(0.0, self._to_float(t.get("paid", 0.0), 0.0))
            due = max(0.0, total_gross - paid)

            discount_pct = max(0.0, self._to_float(t.get("discount", 0.0), 0.0))
            discount_factor = max(0.0, 1.0 - (discount_pct / 100.0))
            items = list(t.get("items") or [])

            prepared_lines = []
            subtotal = 0.0
            for idx, it in enumerate(items):
                pid = self._to_int(it.get("id", 0), 0)
                qty = max(0, self._to_int(it.get("quantity", 0), 0))
                if pid <= 0 or qty <= 0:
                    continue
                unit_sell = self._sale_unit_price(it)
                line_subtotal = max(0.0, unit_sell * float(qty))
                if line_subtotal <= 0.0:
                    continue
                subtotal += line_subtotal
                fallback_unit_cost = max(0.0, self._to_float(product_cost_hint_by_id.get(int(pid), 0.0), 0.0))
                prepared_lines.append(
                    {
                        "line_index": int(idx),
                        "product_id": int(pid),
                        "quantity": int(qty),
                        "unit_sell": float(unit_sell),
                        "line_subtotal": float(line_subtotal),
                        "fallback_unit_cost": float(fallback_unit_cost),
                    }
                )

            if subtotal > 1e-9:
                revenue_net = subtotal * discount_factor
            else:
                # Legacy fallback when sale snapshots are missing.
                revenue_net = total_gross

            invoices[tid] = {
                "id": tid,
                "ts": ts,
                "day": ts.date() if ts else None,
                "user_id": tx_uid,
                "gross_total": total_gross,
                "due": due,
                "revenue": max(0.0, float(revenue_net)),
                "cost": 0.0,
                "profit": 0.0,
                "provisional_open": 0.0,
                "provisional_qty_open": 0.0,
            }

            if prepared_lines:
                sort_ts = ts if ts is not None else datetime.min
                for line in prepared_lines:
                    events.append(
                        (
                            sort_ts,
                            1,  # sales consume after purchases at same timestamp
                            tid,
                            int(line["line_index"]),
                            {
                                "type": "sale",
                                "transaction_id": tid,
                                "product_id": int(line["product_id"]),
                                "quantity": int(line["quantity"]),
                                "fallback_unit_cost": float(line.get("fallback_unit_cost", 0.0) or 0.0),
                            },
                        )
                    )

        for p in purchases or []:
            purchase_id = self._to_int(p.get("id", 0), 0)
            if purchase_id <= 0:
                continue
            ts = self._parse_datetime(p.get("date", ""))
            supplier_id = self._to_int(p.get("supplier_id", 0), 0)
            sort_ts = ts if ts is not None else datetime.min
            items = list(p.get("items") or [])
            for idx, it in enumerate(items):
                pid = self._to_int(it.get("product_id", 0), 0)
                qty = max(0, self._to_int(it.get("quantity", 0), 0))
                if pid <= 0 or qty <= 0:
                    continue
                unit_cost = self._purchase_unit_cost(it)
                events.append(
                    (
                        sort_ts,
                        0,  # purchases add stock first
                        purchase_id,
                        int(idx),
                        {
                            "type": "purchase",
                            "product_id": int(pid),
                            "quantity": int(qty),
                            "unit_cost": float(unit_cost),
                            "supplier_id": int(supplier_id),
                            "purchase_id": int(purchase_id),
                        },
                    )
                )

        events.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        lots_by_product: dict[int, deque] = defaultdict(deque)
        pending_negative_by_product: dict[int, deque] = defaultdict(deque)
        last_known_cost_by_product: dict[int, float] = {}
        invoice_cost: dict[int, float] = defaultdict(float)
        invoice_provisional_open: dict[int, float] = defaultdict(float)
        invoice_provisional_qty_open: dict[int, float] = defaultdict(float)

        for _ts, _priority, _owner, _idx, ev in events:
            etype = str(ev.get("type", ""))
            pid = self._to_int(ev.get("product_id", 0), 0)
            qty = max(0, self._to_int(ev.get("quantity", 0), 0))
            if pid <= 0 or qty <= 0:
                continue

            if etype == "purchase":
                unit_cost = max(0.0, self._to_float(ev.get("unit_cost", 0.0), 0.0))
                if unit_cost <= 1e-9:
                    unit_cost = max(0.0, self._to_float(last_known_cost_by_product.get(pid, 0.0), 0.0))
                last_known_cost_by_product[pid] = unit_cost

                pendq = pending_negative_by_product[pid]
                remaining = float(qty)
                while remaining > 1e-9 and pendq:
                    pending = pendq[0]
                    take = min(float(remaining), float(pending.get("qty_remaining", 0.0) or 0.0))
                    if take <= 1e-9:
                        pendq.popleft()
                        continue
                    tx_id = self._to_int(pending.get("transaction_id", 0), 0)
                    provisional_unit = max(0.0, self._to_float(pending.get("provisional_unit_cost", 0.0), 0.0))
                    provisional_piece = float(take) * provisional_unit
                    actual_piece = float(take) * unit_cost
                    delta = actual_piece - provisional_piece

                    if tx_id > 0:
                        invoice_cost[tx_id] += float(delta)
                        invoice_provisional_open[tx_id] -= float(provisional_piece)
                        invoice_provisional_qty_open[tx_id] -= float(take)

                    pending["qty_remaining"] = max(0.0, float(pending.get("qty_remaining", 0.0) or 0.0) - float(take))
                    remaining -= float(take)
                    if float(pending.get("qty_remaining", 0.0) or 0.0) <= 1e-9:
                        pendq.popleft()

                if remaining > 1e-9:
                    lots_by_product[pid].append(
                        {
                            "qty_remaining": float(remaining),
                            "unit_cost": float(unit_cost),
                            "supplier_id": self._to_int(ev.get("supplier_id", 0), 0),
                            "purchase_id": self._to_int(ev.get("purchase_id", 0), 0),
                        }
                    )
                continue

            if etype == "sale":
                tx_id = self._to_int(ev.get("transaction_id", 0), 0)
                if tx_id <= 0:
                    continue
                fallback_unit_cost = max(0.0, self._to_float(ev.get("fallback_unit_cost", 0.0), 0.0))
                remaining = float(qty)
                line_cost = 0.0
                lotq = lots_by_product[pid]
                while remaining > 1e-9 and lotq:
                    lot = lotq[0]
                    lot_qty = max(0.0, self._to_float(lot.get("qty_remaining", 0.0), 0.0))
                    if lot_qty <= 1e-9:
                        lotq.popleft()
                        continue
                    take = min(remaining, lot_qty)
                    unit_cost = max(0.0, self._to_float(lot.get("unit_cost", 0.0), 0.0))
                    line_cost += float(take) * unit_cost
                    lot["qty_remaining"] = lot_qty - float(take)
                    remaining -= float(take)
                    if self._to_float(lot.get("qty_remaining", 0.0), 0.0) <= 1e-9:
                        lotq.popleft()

                if remaining > 1e-9:
                    provisional_unit = max(0.0, self._to_float(last_known_cost_by_product.get(pid, 0.0), 0.0))
                    if provisional_unit <= 1e-9:
                        provisional_unit = fallback_unit_cost
                    provisional_piece = float(remaining) * provisional_unit
                    line_cost += provisional_piece
                    invoice_provisional_open[tx_id] += provisional_piece
                    invoice_provisional_qty_open[tx_id] += float(remaining)
                    pending_negative_by_product[pid].append(
                        {
                            "transaction_id": int(tx_id),
                            "qty_remaining": float(remaining),
                            "provisional_unit_cost": float(provisional_unit),
                        }
                    )

                invoice_cost[tx_id] += float(line_cost)

        for tx_id, meta in invoices.items():
            cost_val = max(0.0, self._to_float(invoice_cost.get(tx_id, 0.0), 0.0))
            provisional_open_val = max(0.0, self._to_float(invoice_provisional_open.get(tx_id, 0.0), 0.0))
            provisional_qty_open_val = max(0.0, self._to_float(invoice_provisional_qty_open.get(tx_id, 0.0), 0.0))
            revenue_val = max(0.0, self._to_float(meta.get("revenue", 0.0), 0.0))
            meta["cost"] = cost_val
            meta["provisional_open"] = provisional_open_val
            meta["provisional_qty_open"] = provisional_qty_open_val
            meta["profit"] = revenue_val - cost_val

        return invoices

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
        try:
            purchases = self.api.purchases_list() or []
        except Exception:
            purchases = []
        try:
            products = self.api.products(include_inactive=True) or []
        except Exception:
            products = []
        try:
            payments = self.api.transaction_payments_list() or []
        except Exception:
            payments = []

        self._load_user_lookup(docs)
        self._rebuild_user_filter()
        product_cost_hint_by_id: dict[int, float] = {}
        for p in products or []:
            pid = self._to_int(p.get("id", 0), 0)
            if pid <= 0:
                continue
            hint = max(0.0, self._to_float(self._product_cost_hint(p), 0.0))
            if hint > 1e-9:
                product_cost_hint_by_id[pid] = float(hint)
        invoice_map = self._build_invoice_profit_map(docs, purchases, product_cost_hint_by_id=product_cost_hint_by_id)

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
        received_total = 0.0
        due_total = 0.0
        cogs_total = 0.0
        profit_total = 0.0
        realized_profit_total = 0.0
        provisional_total = 0.0
        provisional_qty_total = 0.0

        for tx_id, inv in invoice_map.items():
            tx_uid = self._to_int(inv.get("user_id", 0), 0)
            if uid and tx_uid != uid:
                continue
            day = inv.get("day")
            if day is None:
                continue
            if start_dt and day < start_dt:
                continue
            if end_dt and day > end_dt:
                continue

            sales = max(0.0, self._to_float(inv.get("revenue", 0.0), 0.0))
            due = max(0.0, self._to_float(inv.get("due", 0.0), 0.0))
            cogs = max(0.0, self._to_float(inv.get("cost", 0.0), 0.0))
            profit = self._to_float(inv.get("profit", 0.0), 0.0)
            provisional_open = max(0.0, self._to_float(inv.get("provisional_open", 0.0), 0.0))
            provisional_qty = max(0.0, self._to_float(inv.get("provisional_qty_open", 0.0), 0.0))
            bucket = grouped.setdefault(
                day,
                {
                    "count": 0,
                    "sales": 0.0,
                    "received": 0.0,
                    "due": 0.0,
                    "cogs": 0.0,
                    "profit": 0.0,
                    "realized": 0.0,
                    "provisional": 0.0,
                    "provisional_qty": 0.0,
                },
            )
            bucket["count"] += 1
            bucket["sales"] += sales
            bucket["due"] += due
            bucket["cogs"] += cogs
            bucket["profit"] += profit
            bucket["provisional"] += provisional_open
            bucket["provisional_qty"] += provisional_qty

            tx_count += 1
            gross_total += sales
            due_total += due
            cogs_total += cogs
            profit_total += profit
            provisional_total += provisional_open
            provisional_qty_total += provisional_qty

        for p in payments:
            pay_uid = self._to_int(p.get("user_id", 0), 0)
            if uid and pay_uid != uid:
                continue
            ts = self._parse_datetime(p.get("date", ""))
            if ts is None:
                continue
            day = ts.date()
            if start_dt and day < start_dt:
                continue
            if end_dt and day > end_dt:
                continue
            try:
                amount = float(p.get("amount", 0.0) or 0.0)
            except Exception:
                amount = 0.0
            tx_id = self._to_int(p.get("transaction_id", 0), 0)
            inv = invoice_map.get(tx_id)
            if inv:
                inv_gross = max(0.0, self._to_float(inv.get("gross_total", 0.0), 0.0))
                inv_profit = self._to_float(inv.get("profit", 0.0), 0.0)
                realized_piece = (inv_profit * (amount / inv_gross)) if inv_gross > 1e-9 else 0.0
            else:
                realized_piece = 0.0
            bucket = grouped.setdefault(
                day,
                {
                    "count": 0,
                    "sales": 0.0,
                    "received": 0.0,
                    "due": 0.0,
                    "cogs": 0.0,
                    "profit": 0.0,
                    "realized": 0.0,
                    "provisional": 0.0,
                    "provisional_qty": 0.0,
                },
            )
            bucket["received"] += amount
            bucket["realized"] += realized_piece
            received_total += amount
            realized_profit_total += realized_piece

        self.tx_count_label.setText(str(tx_count))
        self.gross_label.setText(f"{gross_total:.2f}")
        self.paid_label.setText(f"{received_total:.2f}")
        self.due_label.setText(f"{due_total:.2f}")
        self.profit_label.setText(f"{profit_total:.2f}")
        self.realized_profit_label.setText(f"{realized_profit_total:.2f}")
        if provisional_total > 1e-9:
            self.provisional_note.setText(
                f"Provisional open cost in selected range: {provisional_total:.2f} (sales before purchase not fully settled)."
            )
        elif provisional_qty_total > 1e-9:
            self.provisional_note.setText(
                f"Unsettled sale quantity in selected range: {provisional_qty_total:.0f} "
                "(cost reference missing; re-add/edit purchase for accurate profit)."
            )
        else:
            self.provisional_note.setText("All costs in selected range are settled by purchase lots.")

        rows = sorted(grouped.items(), key=lambda item: item[0], reverse=True)
        self.table.setRowCount(0)
        for day, data in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            date_item = QtWidgets.QTableWidgetItem(day.strftime("%d-%m-%Y"))
            count_item = QtWidgets.QTableWidgetItem(str(int(data["count"])))
            gross_item = QtWidgets.QTableWidgetItem(f"{float(data['sales']):.2f}")
            paid_item = QtWidgets.QTableWidgetItem(f"{float(data['received']):.2f}")
            due_item = QtWidgets.QTableWidgetItem(f"{float(data['due']):.2f}")
            cogs_item = QtWidgets.QTableWidgetItem(f"{float(data['cogs']):.2f}")
            profit_item = QtWidgets.QTableWidgetItem(f"{float(data['profit']):.2f}")
            realized_item = QtWidgets.QTableWidgetItem(f"{float(data['realized']):.2f}")
            provisional_item = QtWidgets.QTableWidgetItem(f"{float(data['provisional']):.2f}")

            date_item.setTextAlignment(QtCore.Qt.AlignCenter)
            count_item.setTextAlignment(QtCore.Qt.AlignCenter)
            for itm in (gross_item, paid_item, due_item, cogs_item, profit_item, realized_item, provisional_item):
                itm.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

            self.table.setItem(r, 0, date_item)
            self.table.setItem(r, 1, count_item)
            self.table.setItem(r, 2, gross_item)
            self.table.setItem(r, 3, paid_item)
            self.table.setItem(r, 4, due_item)
            self.table.setItem(r, 5, cogs_item)
            self.table.setItem(r, 6, profit_item)
            self.table.setItem(r, 7, realized_item)
            self.table.setItem(r, 8, provisional_item)
