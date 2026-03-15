from collections import defaultdict, deque
from datetime import datetime, timedelta

from PyQt5 import QtWidgets, QtCore, QtGui

from .ui_common import (
    apply_header_layout,
    apply_page_layout,
    configure_table,
    polish_controls,
    set_secondary,
)


class TrendChartWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: list[str] = []
        self._series: dict[str, list[float]] = {}
        self.setMinimumHeight(250)

    def set_data(self, labels: list[str], series: dict[str, list[float]]):
        self._labels = list(labels or [])
        self._series = {str(k): [float(v or 0.0) for v in (vals or [])] for k, vals in (series or {}).items()}
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 0))

        box = self.rect().adjusted(8, 8, -8, -8)
        painter.setPen(QtGui.QPen(QtGui.QColor("#2f3745"), 1))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#1b212b")))
        painter.drawRoundedRect(box, 10, 10)

        if not self._labels or not self._series:
            painter.setPen(QtGui.QColor("#9db0cb"))
            painter.drawText(box, QtCore.Qt.AlignCenter, "No chart data")
            return

        colors = ["#62A0FF", "#34D399", "#F59E0B", "#A78BFA", "#F87171"]
        series_items = list(self._series.items())

        text_pen = QtGui.QPen(QtGui.QColor("#9db0cb"), 1)
        fm = painter.fontMetrics()

        # Legend layout: measure text and wrap to next row when needed.
        legend_row_h = 18
        legend_gap_x = 14
        legend_marker_w = 16
        legend_left = box.left() + 46
        legend_right = box.right() - 14
        legend_usable_w = max(1, legend_right - legend_left)
        legend_item_widths: list[int] = []
        for name, vals in series_items:
            last_val = float(vals[-1] if vals else 0.0)
            legend_txt = f"{name}: {last_val:.2f}"
            txt_w = fm.horizontalAdvance(legend_txt)
            legend_item_widths.append(int(legend_marker_w + 6 + txt_w + 12))

        legend_rows = 1
        used = 0
        for w in legend_item_widths:
            item_w = min(w, legend_usable_w)
            if used > 0 and (used + item_w) > legend_usable_w:
                legend_rows += 1
                used = item_w + legend_gap_x
            else:
                used += item_w + legend_gap_x
        legend_h = max(22, legend_rows * legend_row_h + 6)

        left = box.left() + 46
        right = box.right() - 22
        top = box.top() + 12 + legend_h
        bottom = box.bottom() - 42
        if right <= left or bottom <= top:
            return
        chart = QtCore.QRect(left, top, right - left, bottom - top)

        max_val = 0.0
        for vals in self._series.values():
            for v in vals:
                max_val = max(max_val, float(v or 0.0))
        max_val = max(1.0, max_val)

        # Grid + Y labels
        grid_pen = QtGui.QPen(QtGui.QColor("#2a3240"), 1)
        for i in range(5):
            ratio = i / 4.0
            y = int(chart.bottom() - ratio * chart.height())
            painter.setPen(grid_pen)
            painter.drawLine(chart.left(), y, chart.right(), y)
            painter.setPen(text_pen)
            val = max_val * ratio
            painter.drawText(box.left() + 6, y - 7, 36, 14, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, f"{val:.0f}")

        # X labels
        n = len(self._labels)
        if n > 0:
            max_ticks = min(7, n)
            if n <= max_ticks:
                x_idx = list(range(n))
            else:
                step = (n - 1) / float(max_ticks - 1)
                x_idx = sorted(set(int(round(i * step)) for i in range(max_ticks)))
                if x_idx[0] != 0:
                    x_idx.insert(0, 0)
                if x_idx[-1] != (n - 1):
                    x_idx.append(n - 1)
            painter.setPen(text_pen)
            label_h = fm.height() + 4
            label_y = chart.bottom() + 10
            for idx in x_idx:
                x = chart.left() if n == 1 else int(chart.left() + idx * (chart.width() / max(1, (n - 1))))
                lbl = str(self._labels[idx] or "")
                label_w = max(56, fm.horizontalAdvance(lbl) + 10)
                if idx == 0:
                    rect = QtCore.QRect(chart.left() + 2, label_y, label_w, label_h)
                    align = QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop
                elif idx == n - 1:
                    rect = QtCore.QRect(chart.right() - label_w - 2, label_y, label_w, label_h)
                    align = QtCore.Qt.AlignRight | QtCore.Qt.AlignTop
                else:
                    rx = max(chart.left(), min(x - (label_w // 2), chart.right() - label_w))
                    rect = QtCore.QRect(rx, label_y, label_w, label_h)
                    align = QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
                painter.drawText(rect, align, lbl)

        # Legend
        lx = chart.left()
        ly = box.top() + 10
        for idx, (name, vals) in enumerate(series_items):
            item_w = legend_item_widths[idx] if idx < len(legend_item_widths) else 110
            item_w = min(int(item_w), legend_usable_w)
            if lx > chart.left() and (lx + item_w) > chart.right():
                lx = chart.left()
                ly += legend_row_h
            color = QtGui.QColor(colors[idx % len(colors)])
            painter.setPen(QtGui.QPen(color, 3))
            painter.drawLine(lx, ly, lx + 16, ly)
            painter.setPen(text_pen)
            last_val = float(vals[-1] if vals else 0.0)
            legend_txt = f"{name}: {last_val:.2f}"
            painter.drawText(lx + 20, ly - 8, item_w - 20, 16, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, legend_txt)
            lx += item_w + legend_gap_x

        # Series lines
        for idx, (_name, vals) in enumerate(series_items):
            if not vals:
                continue
            color = QtGui.QColor(colors[idx % len(colors)])
            pen = QtGui.QPen(color, 2)
            painter.setPen(pen)
            points: list[QtCore.QPoint] = []
            for i, raw_v in enumerate(vals):
                v = max(0.0, float(raw_v or 0.0))
                x = chart.left() if len(vals) == 1 else int(chart.left() + i * (chart.width() / max(1, (len(vals) - 1))))
                y = int(chart.bottom() - (v / max_val) * chart.height())
                points.append(QtCore.QPoint(x, y))
            for i in range(1, len(points)):
                painter.drawLine(points[i - 1], points[i])
            painter.setBrush(QtGui.QBrush(color))
            for p in points:
                painter.drawEllipse(p, 2, 2)


class BarChartWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: list[str] = []
        self._values: list[float] = []
        self.setMinimumHeight(250)

    def set_data(self, labels: list[str], values: list[float]):
        self._labels = [str(x or "") for x in (labels or [])]
        self._values = [float(x or 0.0) for x in (values or [])]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 0))

        box = self.rect().adjusted(8, 8, -8, -8)
        painter.setPen(QtGui.QPen(QtGui.QColor("#2f3745"), 1))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#1b212b")))
        painter.drawRoundedRect(box, 10, 10)

        if not self._labels or not self._values:
            painter.setPen(QtGui.QColor("#9db0cb"))
            painter.drawText(box, QtCore.Qt.AlignCenter, "No chart data")
            return

        fm = painter.fontMetrics()
        left = box.left() + 20
        right = box.right() - 18
        top = box.top() + 24
        n = min(len(self._labels), len(self._values))
        if n <= 0:
            return
        usable_w = max(1, right - left)
        avg_slot = usable_w / float(n)
        rotate_labels = avg_slot < 72.0
        bottom_pad = 72 if rotate_labels else 48
        bottom = box.bottom() - bottom_pad
        if right <= left or bottom <= top:
            return
        chart = QtCore.QRect(left, top, right - left, bottom - top)

        max_val = max(1.0, max(self._values[:n]))
        scale_max = max_val * 1.20
        slot_w = chart.width() / float(n)
        bar_w = max(8.0, min(42.0, slot_w * 0.62))

        baseline_pen = QtGui.QPen(QtGui.QColor("#2a3240"), 1)
        painter.setPen(baseline_pen)
        painter.drawLine(chart.left(), chart.bottom(), chart.right(), chart.bottom())

        for i in range(n):
            value = max(0.0, float(self._values[i] or 0.0))
            ratio = value / scale_max
            h = max(0, int(ratio * chart.height()))
            x = int(chart.left() + i * slot_w + (slot_w - bar_w) / 2.0)
            y = chart.bottom() - h
            bar_rect = QtCore.QRect(x, y, int(bar_w), h)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#62A0FF")))
            painter.drawRoundedRect(bar_rect, 4, 4)

            painter.setPen(QtGui.QColor("#9db0cb"))
            label_w = max(int(bar_w) + 28, int(slot_w) - 6)
            label_w = min(label_w, int(slot_w))
            label_x = int(chart.left() + i * slot_w + (slot_w - label_w) / 2.0)
            max_chars = max(10, min(28, int(label_w / 7)))
            label_txt = self._short(self._labels[i], 18 if rotate_labels else max_chars)
            if rotate_labels:
                painter.save()
                anchor_x = int(chart.left() + i * slot_w + (slot_w / 2.0))
                anchor_y = chart.bottom() + 20
                painter.translate(anchor_x, anchor_y)
                painter.rotate(-35)
                painter.drawText(QtCore.QRect(-70, -10, 140, fm.height() + 6), QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter, label_txt)
                painter.restore()
            else:
                painter.drawText(label_x, chart.bottom() + 10, label_w, fm.height() + 4, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, label_txt)

            painter.setPen(QtGui.QColor("#d6e3f7"))
            qty_txt = f"{value:.0f}"
            qty_w = max(int(bar_w) + 30, fm.horizontalAdvance(qty_txt) + 12)
            qty_x = int(chart.left() + i * slot_w + (slot_w - qty_w) / 2.0)
            qty_h = fm.height() + 6
            # Prefer drawing just above the bar; if that would clip
            # against the top of the chart, draw slightly inside the bar
            # instead so large values remain fully visible.
            preferred_top = y - qty_h - 6
            if preferred_top >= chart.top() + 4:
                qty_y = preferred_top
            else:
                qty_y = min(chart.bottom() - qty_h - 4, y + 4)
            painter.drawText(qty_x, qty_y, qty_w, qty_h, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, qty_txt)

    def _short(self, text: str, max_len: int) -> str:
        txt = str(text or "")
        if len(txt) <= max_len:
            return txt
        return txt[: max_len - 1] + "."


class DashboardView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        apply_page_layout(root)

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

        self.btn_reset = QtWidgets.QPushButton("Reset")
        set_secondary(self.btn_reset)
        filters.addWidget(self.btn_reset)
        filters.addStretch(1)
        root.addLayout(filters)

        metrics = QtWidgets.QHBoxLayout()
        apply_header_layout(metrics)
        sales_card, self.sales_lbl = self._metric_card("Sales", "0.00")
        cash_card, self.cash_lbl = self._metric_card("Cash Received", "0.00")
        due_card, self.due_lbl = self._metric_card("Due", "0.00")
        profit_card, self.profit_lbl = self._metric_card("Profit (Accrual)", "0.00")
        realized_card, self.realized_profit_lbl = self._metric_card("Profit (Cash)", "0.00")
        purchases_card, self.purchases_lbl = self._metric_card("Purchases", "0.00")
        supplier_due_card, self.supplier_due_lbl = self._metric_card("Supplier Due", "0.00")
        tx_card, self.tx_lbl = self._metric_card("Transactions", "0")
        low_stock_card, self.low_stock_lbl = self._metric_card("Low Stock", "0")
        metrics.addWidget(sales_card)
        metrics.addWidget(cash_card)
        metrics.addWidget(due_card)
        metrics.addWidget(profit_card)
        metrics.addWidget(realized_card)
        metrics.addWidget(purchases_card)
        metrics.addWidget(supplier_due_card)
        metrics.addWidget(tx_card)
        metrics.addWidget(low_stock_card)
        root.addLayout(metrics)

        charts = QtWidgets.QHBoxLayout()
        apply_header_layout(charts)
        trend_box = QtWidgets.QGroupBox("Daily Trend")
        trend_box.setObjectName("totalsCard")
        trend_v = QtWidgets.QVBoxLayout(trend_box)
        trend_v.setContentsMargins(10, 10, 10, 10)
        self.trend_chart = TrendChartWidget()
        trend_v.addWidget(self.trend_chart)

        top_box = QtWidgets.QGroupBox("Top Selling Products (Qty)")
        top_box.setObjectName("totalsCard")
        top_v = QtWidgets.QVBoxLayout(top_box)
        top_v.setContentsMargins(10, 10, 10, 10)
        self.top_chart = BarChartWidget()
        top_v.addWidget(self.top_chart)

        charts.addWidget(trend_box, 2)
        charts.addWidget(top_box, 1)
        root.addLayout(charts, 1)

        bottoms = QtWidgets.QHBoxLayout()
        apply_header_layout(bottoms)

        low_box = QtWidgets.QGroupBox("Low Stock Alerts")
        low_box.setObjectName("totalsCard")
        low_v = QtWidgets.QVBoxLayout(low_box)
        low_v.setContentsMargins(10, 10, 10, 10)
        self.low_table = QtWidgets.QTableWidget(0, 3)
        self.low_table.setHorizontalHeaderLabels(["Product", "Qty", "Company"])
        configure_table(self.low_table, stretch_last=False)
        low_hdr = self.low_table.horizontalHeader()
        low_hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        low_hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        low_hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        low_v.addWidget(self.low_table)
        bottoms.addWidget(low_box, 1)

        act_box = QtWidgets.QGroupBox("Recent Activity")
        act_box.setObjectName("totalsCard")
        act_v = QtWidgets.QVBoxLayout(act_box)
        act_v.setContentsMargins(10, 10, 10, 10)
        self.activity_table = QtWidgets.QTableWidget(0, 4)
        self.activity_table.setHorizontalHeaderLabels(["Date", "Type", "Reference", "Amount"])
        configure_table(self.activity_table, stretch_last=False)
        act_hdr = self.activity_table.horizontalHeader()
        act_hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        act_hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        act_hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        act_hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        act_v.addWidget(self.activity_table)
        bottoms.addWidget(act_box, 1)

        root.addLayout(bottoms, 1)

        self.status_note = QtWidgets.QLabel("")
        self.status_note.setObjectName("mutedLabel")
        root.addWidget(self.status_note)

        self.start.dateChanged.connect(self.refresh)
        self.end.dateChanged.connect(self.refresh)
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
        self.start.setDate(QtCore.QDate.currentDate().addDays(-29))
        self.end.setDate(QtCore.QDate.currentDate())
        self.start.blockSignals(False)
        self.end.blockSignals(False)
        self.refresh()

    def _to_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value if value is not None else default)
        except Exception:
            return float(default)

    def _to_int(self, value, default: int = 0) -> int:
        try:
            return int(value if value is not None else default)
        except Exception:
            return int(default)

    def _parse_datetime(self, raw_value):
        txt = str(raw_value or "").strip()
        if not txt:
            return None
        try:
            return datetime.fromisoformat(txt.replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            normalized = txt.replace("T", " ").split(".", 1)[0]
            return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        try:
            return datetime.strptime(txt, "%Y-%m-%d")
        except Exception:
            return None

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
            total_gross = max(0.0, self._to_float(t.get("total", 0.0), 0.0))
            paid = max(0.0, self._to_float(t.get("paid", 0.0), 0.0))
            due = max(0.0, total_gross - paid)
            discount_pct = max(0.0, self._to_float(t.get("discount", 0.0), 0.0))
            discount_factor = max(0.0, 1.0 - (discount_pct / 100.0))
            items = list(t.get("items") or [])

            subtotal = 0.0
            prepared_lines = []
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
                prepared_lines.append((int(idx), int(pid), int(qty), float(fallback_unit_cost)))

            revenue_net = (subtotal * discount_factor) if subtotal > 1e-9 else total_gross
            invoices[tid] = {
                "id": tid,
                "ts": ts,
                "day": ts.date() if ts else None,
                "gross_total": total_gross,
                "revenue": max(0.0, float(revenue_net)),
                "due": due,
                "cost": 0.0,
                "profit": 0.0,
            }

            if prepared_lines:
                sort_ts = ts if ts is not None else datetime.min
                for idx, pid, qty, fallback_unit_cost in prepared_lines:
                    events.append(
                        (
                            sort_ts,
                            1,  # sale after purchase at same timestamp
                            tid,
                            idx,
                            {
                                "type": "sale",
                                "transaction_id": tid,
                                "product_id": pid,
                                "quantity": qty,
                                "fallback_unit_cost": float(fallback_unit_cost),
                            },
                        )
                    )

        for p in purchases or []:
            purchase_id = self._to_int(p.get("id", 0), 0)
            if purchase_id <= 0:
                continue
            ts = self._parse_datetime(p.get("date", ""))
            sort_ts = ts if ts is not None else datetime.min
            supplier_id = self._to_int(p.get("supplier_id", 0), 0)
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
                        0,
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
                remaining = float(qty)
                pendq = pending_negative_by_product[pid]
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
                    if tx_id > 0:
                        invoice_cost[tx_id] += float(actual_piece - provisional_piece)
                    pending["qty_remaining"] = max(0.0, float(pending.get("qty_remaining", 0.0) or 0.0) - float(take))
                    remaining -= float(take)
                    if float(pending.get("qty_remaining", 0.0) or 0.0) <= 1e-9:
                        pendq.popleft()
                if remaining > 1e-9:
                    lots_by_product[pid].append({"qty_remaining": float(remaining), "unit_cost": float(unit_cost)})
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
                    line_cost += float(remaining) * provisional_unit
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
            revenue_val = max(0.0, self._to_float(meta.get("revenue", 0.0), 0.0))
            meta["cost"] = cost_val
            meta["profit"] = revenue_val - cost_val
        return invoices

    def refresh(self):
        try:
            transactions = self.api.transactions_list() or []
        except Exception:
            transactions = []
        try:
            purchases = self.api.purchases_list() or []
        except Exception:
            purchases = []
        try:
            payments = self.api.transaction_payments_list() or []
        except Exception:
            payments = []
        try:
            products = self.api.products() or []
        except Exception:
            products = []

        try:
            start_dt = self.start.date().toPyDate()
            end_dt = self.end.date().toPyDate()
        except Exception:
            now = datetime.now().date()
            start_dt = now - timedelta(days=29)
            end_dt = now
        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt

        def in_range(day):
            return day is not None and start_dt <= day <= end_dt

        sales_total = 0.0
        due_total = 0.0
        profit_total = 0.0
        realized_profit_total = 0.0
        purchases_total = 0.0
        supplier_due_total = 0.0
        cash_total = 0.0
        tx_count = 0

        sales_by_day = defaultdict(float)
        due_by_day = defaultdict(float)
        profit_by_day = defaultdict(float)
        realized_profit_by_day = defaultdict(float)
        purchases_by_day = defaultdict(float)
        cash_by_day = defaultdict(float)
        sold_qty_by_product = defaultdict(float)
        product_name_by_id: dict[int, str] = {}

        product_cost_hint_by_id: dict[int, float] = {}
        for p in products or []:
            pid = self._to_int(p.get("id", 0), 0)
            if pid <= 0:
                continue
            hint = max(0.0, self._to_float(self._product_cost_hint(p), 0.0))
            if hint > 1e-9:
                product_cost_hint_by_id[pid] = float(hint)

        invoice_map = self._build_invoice_profit_map(
            transactions,
            purchases,
            product_cost_hint_by_id=product_cost_hint_by_id,
        )

        for p in products or []:
            pid = self._to_int(p.get("id", 0), 0)
            if pid > 0:
                product_name_by_id[pid] = str(p.get("name", "") or f"ID {pid}")

        for tx in transactions or []:
            tdt = self._parse_datetime(tx.get("date", ""))
            day = tdt.date() if tdt else None
            if not in_range(day):
                continue
            total = max(0.0, self._to_float(tx.get("total", 0.0), 0.0))
            paid = max(0.0, self._to_float(tx.get("paid", 0.0), 0.0))
            sales_total += total
            due_val = max(0.0, total - paid)
            due_total += due_val
            tx_count += 1
            sales_by_day[day] += total
            due_by_day[day] += due_val
            for it in (tx.get("items") or []):
                pid = self._to_int(it.get("id", 0), 0)
                qty = max(0.0, self._to_float(it.get("quantity", 0), 0.0))
                if pid > 0 and qty > 0:
                    sold_qty_by_product[pid] += qty
                    if pid not in product_name_by_id:
                        product_name_by_id[pid] = str(it.get("name", "") or f"ID {pid}")

        for inv in invoice_map.values():
            day = inv.get("day")
            if not in_range(day):
                continue
            pval = self._to_float(inv.get("profit", 0.0), 0.0)
            profit_total += pval
            profit_by_day[day] += pval

        for pc in purchases or []:
            supplier_due_total += max(
                0.0,
                max(0.0, self._to_float(pc.get("total", 0.0), 0.0))
                - max(0.0, self._to_float(pc.get("paid", 0.0), 0.0)),
            )
            pdt = self._parse_datetime(pc.get("date", ""))
            day = pdt.date() if pdt else None
            if not in_range(day):
                continue
            amount = max(0.0, self._to_float(pc.get("total", 0.0), 0.0))
            purchases_total += amount
            purchases_by_day[day] += amount

        for pay in payments or []:
            pdt = self._parse_datetime(pay.get("date", ""))
            day = pdt.date() if pdt else None
            if not in_range(day):
                continue
            amount = self._to_float(pay.get("amount", 0.0), 0.0)
            cash_total += amount
            cash_by_day[day] += amount

            tx_id = self._to_int(pay.get("transaction_id", 0), 0)
            inv = invoice_map.get(tx_id)
            if inv:
                inv_gross = max(0.0, self._to_float(inv.get("gross_total", 0.0), 0.0))
                inv_profit = self._to_float(inv.get("profit", 0.0), 0.0)
                realized_piece = (inv_profit * (amount / inv_gross)) if inv_gross > 1e-9 else 0.0
            else:
                realized_piece = 0.0
            realized_profit_total += realized_piece
            realized_profit_by_day[day] += realized_piece

        days = []
        cur = start_dt
        while cur <= end_dt:
            days.append(cur)
            cur = cur + timedelta(days=1)
        labels = [d.strftime("%d-%m") for d in days]
        self.trend_chart.set_data(
            labels,
            {
                "Sales": [float(sales_by_day.get(d, 0.0)) for d in days],
                "Cash": [float(cash_by_day.get(d, 0.0)) for d in days],
                "Purchases": [float(purchases_by_day.get(d, 0.0)) for d in days],
                "Due": [float(due_by_day.get(d, 0.0)) for d in days],
                "Profit": [float(profit_by_day.get(d, 0.0)) for d in days],
            },
        )

        top_items = sorted(sold_qty_by_product.items(), key=lambda x: float(x[1]), reverse=True)[:8]
        top_labels = [product_name_by_id.get(pid, f"ID {pid}") for pid, _ in top_items]
        top_vals = [float(qty) for _, qty in top_items]
        self.top_chart.set_data(top_labels, top_vals)

        low_rows = []
        for p in products or []:
            qty = self._to_int(p.get("quantity", 0), 0)
            if qty <= 5:
                low_rows.append(
                    (
                        str(p.get("name", "") or ""),
                        int(qty),
                        str(p.get("company_name", "") or ""),
                    )
                )
        low_rows.sort(key=lambda x: (x[1], x[0].lower()))
        self.low_table.setRowCount(0)
        for name, qty, company in low_rows[:20]:
            r = self.low_table.rowCount()
            self.low_table.insertRow(r)
            self.low_table.setItem(r, 0, QtWidgets.QTableWidgetItem(name))
            qty_item = QtWidgets.QTableWidgetItem(str(int(qty)))
            qty_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.low_table.setItem(r, 1, qty_item)
            self.low_table.setItem(r, 2, QtWidgets.QTableWidgetItem(company))

        activities = []
        for tx in transactions or []:
            tdt = self._parse_datetime(tx.get("date", ""))
            day = tdt.date() if tdt else None
            if not in_range(day):
                continue
            tx_id = self._to_int(tx.get("id", 0), 0)
            amount = max(0.0, self._to_float(tx.get("total", 0.0), 0.0))
            activities.append((tdt, "Sale", f"INV #{tx_id}", amount))
        for pc in purchases or []:
            pdt = self._parse_datetime(pc.get("date", ""))
            day = pdt.date() if pdt else None
            if not in_range(day):
                continue
            pid = self._to_int(pc.get("id", 0), 0)
            amount = max(0.0, self._to_float(pc.get("total", 0.0), 0.0))
            activities.append((pdt, "Purchase", f"PO #{pid}", -amount))
        for pay in payments or []:
            pdt = self._parse_datetime(pay.get("date", ""))
            day = pdt.date() if pdt else None
            if not in_range(day):
                continue
            tx_id = self._to_int(pay.get("transaction_id", 0), 0)
            amount = self._to_float(pay.get("amount", 0.0), 0.0)
            activities.append((pdt, "Payment", f"INV #{tx_id}", amount))

        activities.sort(key=lambda x: x[0] or datetime.min, reverse=True)
        self.activity_table.setRowCount(0)
        for tdt, kind, ref, amount in activities[:20]:
            r = self.activity_table.rowCount()
            self.activity_table.insertRow(r)
            dt_txt = tdt.strftime("%d-%m-%Y %H:%M") if tdt else ""
            self.activity_table.setItem(r, 0, QtWidgets.QTableWidgetItem(dt_txt))
            self.activity_table.setItem(r, 1, QtWidgets.QTableWidgetItem(kind))
            self.activity_table.setItem(r, 2, QtWidgets.QTableWidgetItem(ref))
            amount_item = QtWidgets.QTableWidgetItem(f"{amount:+.2f}")
            amount_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            if amount < 0:
                amount_item.setForeground(QtGui.QBrush(QtGui.QColor("#F87171")))
            elif amount > 0:
                amount_item.setForeground(QtGui.QBrush(QtGui.QColor("#34D399")))
            self.activity_table.setItem(r, 3, amount_item)

        self.sales_lbl.setText(f"{sales_total:.2f}")
        self.cash_lbl.setText(f"{cash_total:.2f}")
        self.due_lbl.setText(f"{due_total:.2f}")
        self.profit_lbl.setText(f"{profit_total:.2f}")
        self.realized_profit_lbl.setText(f"{realized_profit_total:.2f}")
        self.purchases_lbl.setText(f"{purchases_total:.2f}")
        self.supplier_due_lbl.setText(f"{supplier_due_total:.2f}")
        self.tx_lbl.setText(str(int(tx_count)))
        self.low_stock_lbl.setText(str(int(len(low_rows))))
        self.status_note.setText(
            f"Range: {start_dt.isoformat()} to {end_dt.isoformat()} | "
            f"Sales {sales_total:.2f} | Cash {cash_total:.2f} | Due {due_total:.2f} | "
            f"Supplier Due {supplier_due_total:.2f} | Profit {profit_total:.2f}"
        )
