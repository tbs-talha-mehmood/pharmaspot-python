from datetime import datetime

from PyQt5 import QtWidgets, QtCore, QtGui
from .ui_common import (
    apply_form_layout,
    apply_header_layout,
    apply_page_layout,
    configure_table,
    fit_dialog_to_contents,
    polish_controls,
    set_accent,
    set_danger,
    set_secondary,
)


class PurchasesView(QtWidgets.QWidget):
    inventory_changed = QtCore.pyqtSignal()
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user_id: int = 0
        self._is_admin: bool = False
        self._can_edit_invoice: bool = False
        self._can_delete_payment: bool = False
        self._products_cache = None
        self._history_page = 1
        self._history_pages = 1
        self._build()
        self.refresh_history()

    def set_user(self, user: dict):
        u = user or {}
        try:
            self.user_id = int(u.get("id", 0) or 0)
        except Exception:
            self.user_id = 0
        uname = str(u.get("username", "") or "").strip().lower()
        self._is_admin = bool(self.user_id == 1 or uname == "admin")
        self._can_edit_invoice = bool(u.get("perm_edit_invoice", False) or self._is_admin)
        self._can_delete_payment = bool(u.get("perm_delete_payment", False) or self._is_admin)
        # History delete button mirrors invoice delete permission
        self.btn_delete.setEnabled(self._can_edit_invoice)

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self.new_tab = QtWidgets.QWidget()
        self.history_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.new_tab, "New Purchase")
        self.tabs.addTab(self.history_tab, "History")

        self._build_new_purchase(self.new_tab)
        self._build_history(self.history_tab)

    def _build_new_purchase(self, parent):
        v = QtWidgets.QVBoxLayout(parent)
        apply_page_layout(v)

        top_row = QtWidgets.QHBoxLayout()
        apply_header_layout(top_row)
        top_row.setSpacing(8)
        top_row.addWidget(QtWidgets.QLabel("Supplier"))
        self.supplier_cb = QtWidgets.QComboBox()
        self.supplier_cb.setEditable(True)
        self.supplier_cb.setMinimumWidth(260)
        supplier_line = self.supplier_cb.lineEdit()
        if supplier_line is not None:
            supplier_line.returnPressed.connect(self._focus_search)
        self._load_suppliers()
        top_row.addWidget(self.supplier_cb)
        top_row.addWidget(QtWidgets.QLabel("Product"))

        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("mainSearchInput")
        self.search.setPlaceholderText("Search product by name")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(40)
        self.search.textChanged.connect(self._on_search_changed)
        self.search.returnPressed.connect(self._add_first_search_result)
        self.search.installEventFilter(self)
        top_row.addWidget(self.search, 1)
        v.addLayout(top_row)

        self.results = QtWidgets.QListWidget(parent)
        self.results.setObjectName("searchResultsPopup")
        self.results.setVisible(False)
        self.results.setMaximumHeight(240)
        self.results.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.results.itemActivated.connect(self._on_result_activate)
        self.results.installEventFilter(self)

        self.items_table = QtWidgets.QTableWidget(0, 7)
        self.items_table.setObjectName("posCartTable")
        self.items_table.setHorizontalHeaderLabels(
            ["Product", "Retail", "% Discount", "Trade", "Addl %", "Qty", "Line Total"]
        )
        configure_table(self.items_table, stretch_last=False)
        self.items_table.verticalHeader().setDefaultSectionSize(40)
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        col_widths = {
            1: 132,
            2: 102,
            3: 132,
            4: 102,
            5: 92,
            6: 152,
        }
        for col, width in col_widths.items():
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
            self.items_table.setColumnWidth(col, width)
        v.addWidget(self.items_table)
        self._suppress_item_change = False
        # Enable keyboard navigation within the items table
        self.items_table.installEventFilter(self)

        btns_bar = QtWidgets.QHBoxLayout()
        self.btn_remove = QtWidgets.QPushButton("Remove Item")
        self.btn_clear = QtWidgets.QPushButton("Clear")
        set_secondary(self.btn_remove, self.btn_clear)
        btns_bar.addWidget(self.btn_remove)
        btns_bar.addWidget(self.btn_clear)
        btns_bar.addStretch(1)
        v.addLayout(btns_bar)

        total_bar = QtWidgets.QHBoxLayout()
        total_bar.addWidget(QtWidgets.QLabel("Paid"))
        self.paid_input = QtWidgets.QDoubleSpinBox()
        self.paid_input.setDecimals(2)
        self.paid_input.setRange(0.0, 10**12)
        self.paid_input.setSingleStep(50.0)
        self.paid_input.setMinimumWidth(140)
        total_bar.addWidget(self.paid_input)
        total_bar.addStretch(1)
        self.total_label = QtWidgets.QLabel("Total: 0.00")
        self.total_label.setObjectName("moneyStrong")
        total_bar.addWidget(self.total_label)
        self.due_label = QtWidgets.QLabel("Due: 0.00")
        self.due_label.setObjectName("moneyStrong")
        total_bar.addWidget(self.due_label)
        v.addLayout(total_bar)

        action_bar = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save Purchase")
        self.btn_cancel_edit = QtWidgets.QPushButton("Cancel Edit")
        set_accent(self.btn_save)
        set_danger(self.btn_cancel_edit)
        self.btn_cancel_edit.setVisible(False)
        action_bar.addStretch(1)
        action_bar.addWidget(self.btn_cancel_edit)
        action_bar.addWidget(self.btn_save)
        v.addLayout(action_bar)

        self.btn_remove.clicked.connect(self._remove_item)
        self.btn_clear.clicked.connect(self._clear_items)
        self.btn_save.clicked.connect(self._save_purchase)
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        self.paid_input.valueChanged.connect(self._recalc_total)
        polish_controls(parent)
        # Keyboard shortcuts similar to POS
        QtWidgets.QShortcut(QtGui.QKeySequence("F2"), self, activated=self._focus_search)
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self, activated=self._remove_item)

    def _build_history(self, parent):
        v = QtWidgets.QVBoxLayout(parent)
        apply_page_layout(v)
        header = QtWidgets.QHBoxLayout()
        apply_header_layout(header)
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        set_secondary(self.btn_edit)
        set_danger(self.btn_delete)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        v.addLayout(header)

        self.history_table = QtWidgets.QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(["ID", "Date", "Time", "Supplier", "Items", "Total"])
        configure_table(self.history_table, stretch_last=False)
        self.history_table.verticalHeader().setDefaultSectionSize(36)
        history_hdr = self.history_table.horizontalHeader()
        history_hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        history_hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        history_hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        history_hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)
        history_hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.Fixed)
        self.history_table.setColumnWidth(1, 120)
        self.history_table.setColumnWidth(2, 96)
        self.history_table.setColumnWidth(4, 84)
        self.history_table.setColumnWidth(5, 128)
        self.history_table.setColumnHidden(0, True)
        v.addWidget(self.history_table)

        pager = QtWidgets.QHBoxLayout()
        self.history_btn_prev = QtWidgets.QPushButton("Prev")
        self.history_btn_next = QtWidgets.QPushButton("Next")
        set_secondary(self.history_btn_prev, self.history_btn_next)
        self.history_page_label = QtWidgets.QLabel("Page 1 / 1")
        self.history_page_label.setObjectName("mutedLabel")
        pager.addWidget(self.history_btn_prev)
        pager.addWidget(self.history_btn_next)
        pager.addWidget(self.history_page_label)
        pager.addStretch(1)
        v.addLayout(pager)

        self.btn_edit.clicked.connect(self._edit_selected)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.history_btn_prev.clicked.connect(self._prev_history_page)
        self.history_btn_next.clicked.connect(self._next_history_page)
        polish_controls(parent)

    def refresh(self):
        """Refresh purchase data when module is opened from sidebar."""
        try:
            self._load_suppliers()
        except Exception:
            pass
        try:
            self._load_products(force=True)
        except Exception:
            pass
        self.refresh_history()
        try:
            self._on_search_changed(self.search.text())
        except Exception:
            pass

    def _prev_history_page(self):
        if self._history_page > 1:
            self._history_page -= 1
            self.refresh_history()

    def _next_history_page(self):
        if self._history_page < self._history_pages:
            self._history_page += 1
            self.refresh_history()

    def _load_products(self, force: bool = False):
        if force or self._products_cache is None:
            self._products_cache = self.api.products() or []
        return self._products_cache

    def _load_suppliers(self):
        self.supplier_cb.clear()
        self.supplier_cb.addItem("Select or type name", 0)
        try:
            for s in self.api.suppliers() or []:
                self.supplier_cb.addItem(s.get("name", ""), int(s.get("id")))
        except Exception:
            pass


    def _product_picker(self, parent):
        d = QtWidgets.QDialog(parent)
        d.setWindowTitle("Add Item")
        v = QtWidgets.QVBoxLayout(d)
        apply_page_layout(v)
        products = self._load_products(force=True)
        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("Search product by name")
        search.setClearButtonEnabled(True)
        results = QtWidgets.QListWidget()
        results.setMinimumHeight(200)
        v.addWidget(search)
        v.addWidget(results)
        qty = QtWidgets.QSpinBox()
        qty.setRange(1, 10**9)
        qty.setValue(1)
        retail = QtWidgets.QDoubleSpinBox()
        retail.setMaximum(10**9)
        retail.setDecimals(2)
        retail.setValue(0.0)
        trade = QtWidgets.QDoubleSpinBox()
        trade.setMaximum(10**9)
        trade.setDecimals(2)
        trade.setValue(0.0)
        available_lbl = QtWidgets.QLabel("Available: -")
        form = QtWidgets.QFormLayout()
        apply_form_layout(form)
        form.addRow("Quantity", qty)
        form.addRow("Retail Price", retail)
        form.addRow("Trade Price", trade)
        form.addRow("In Stock", available_lbl)
        v.addLayout(form)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        v.addWidget(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=520, fixed=True)

        def _populate(term: str):
            results.clear()
            needle = term.strip().lower()
            if not needle:
                return
            for p in products:
                name = str(p.get("name", ""))
                if needle in name.lower():
                    company = str(p.get("company_name", ""))
                    qty_avail = p.get("quantity", 0)
                    label = f"{name} ({company})" if company else name
                    label = f"{label} - Stock: {qty_avail}"
                    item = QtWidgets.QListWidgetItem(label)
                    item.setData(QtCore.Qt.UserRole, int(p.get("id")))
                    results.addItem(item)

        def _sync_price():
            item = results.currentItem()
            if not item:
                return
            pid = int(item.data(QtCore.Qt.UserRole))
            prod = next((p for p in products if int(p.get("id")) == pid), None)
            if prod:
                try:
                    retail.setValue(float(prod.get("price", 0.0)))
                    trade.setValue(float(prod.get("price", 0.0)))
                except Exception:
                    pass
                try:
                    available_lbl.setText(f"Available: {int(prod.get('quantity', 0) or 0)}")
                except Exception:
                    available_lbl.setText("Available: -")

        search.textChanged.connect(_populate)
        results.currentItemChanged.connect(lambda _cur, _prev: _sync_price())
        return d, results, qty, retail, trade

    def _make_money_spin(self, value):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setMaximum(10**9)
        spin.setDecimals(2)
        spin.setValue(float(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        spin.setObjectName("cartEditor")
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setMinimumHeight(28)
        return spin

    def _make_pct_spin(self, value):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setDecimals(2)
        spin.setValue(float(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        spin.setObjectName("cartEditor")
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setMinimumHeight(28)
        return spin

    def _make_qty_spin(self, value):
        spin = QtWidgets.QSpinBox()
        spin.setRange(1, 10**9)
        spin.setValue(int(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        spin.setObjectName("cartEditor")
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setMinimumHeight(28)
        return spin

    # ---------- Search like POS ----------
    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _position_results_popup(self):
        if self.results.count() <= 0:
            return
        popup_h = min(self.results.sizeHintForRow(0) * min(self.results.count(), 7) + 10, self.results.maximumHeight())
        top_left = self.search.mapTo(self.new_tab, QtCore.QPoint(0, self.search.height() + 4))
        popup_w = self.search.width()
        bottom_space = self.new_tab.height() - top_left.y() - 10
        if bottom_space < popup_h:
            above_y = self.search.mapTo(self.new_tab, QtCore.QPoint(0, -popup_h - 4)).y()
            if above_y >= 6:
                top_left.setY(above_y)
            else:
                popup_h = max(90, bottom_space)
        self.results.setGeometry(top_left.x(), top_left.y(), popup_w, popup_h)
        self.results.raise_()

    def _show_results_popup(self):
        if self.results.count() <= 0:
            self._hide_results_popup()
            return
        self._position_results_popup()
        self.results.show()
        self.results.raise_()

    def _hide_results_popup(self):
        if self.results.isVisible():
            self.results.hide()

    def _on_search_changed(self, text: str):
        text_raw = (text or "").strip()
        text_l = text_raw.lower()
        self.results.clear()
        products = self._load_products()
        if not text_l:
            self._hide_results_popup()
            return
        count = 0
        for p in products:
            try:
                name = str(p.get("name", ""))
                company = str(p.get("company_name", ""))
                pid = str(p.get("id", ""))
                if (
                    text_l in name.lower()
                    or (company and text_l in company.lower())
                    or (text_raw.isdigit() and text_raw == pid)
                ):
                    qty_avail = p.get("quantity", 0)
                    label = f"{name} ({company})" if company else name
                    label = f"{label} - Stock: {qty_avail}"
                    item = QtWidgets.QListWidgetItem(label)
                    item.setData(QtCore.Qt.UserRole, int(p.get("id")))
                    self.results.addItem(item)
                    count += 1
                    if count >= 100:
                        break
            except Exception:
                pass
        if self.results.count() > 0:
            self.results.setCurrentRow(0)
            self._show_results_popup()
        else:
            self._hide_results_popup()

    def _add_first_search_result(self):
        item = self.results.currentItem() if self.results.isVisible() else None
        if item is None and self.results.count() > 0:
            item = self.results.item(0)
        if item is None:
            return
        self._on_result_activate(item)

    def _on_result_activate(self, item: QtWidgets.QListWidgetItem):
        pid = int(item.data(QtCore.Qt.UserRole) or 0)
        products = self._load_products()
        prod = next((p for p in products if int(p.get("id", 0) or 0) == pid), None)
        if not prod:
            return
        row = self._add_product_to_table(prod)
        if row is None:
            return
        self.search.clear()
        self._hide_results_popup()

    def _add_product_to_table(self, product: dict):
        existing = self._find_row_for_product(int(product.get("id", 0) or 0))
        if existing is not None:
            QtWidgets.QMessageBox.warning(self, "Already added", "This product is already in the list.")
            self._focus_items_cell(existing, 1)
            return None
        name = str(product.get("name", ""))
        company = str(product.get("company_name", ""))
        label = f"{name} ({company})" if company else name
        pid = int(product.get("id", 0) or 0)
        company_id = int(product.get("company_id", 0) or 0)
        retail = float(product.get("price", 0.0) or 0.0)
        discount = float(product.get("discount_pct", product.get("purchase_discount", 0.0)) or 0.0)
        trade = product.get("trade_price")
        if trade is None:
            try:
                trade = retail * (1.0 - (discount / 100.0))
            except Exception:
                trade = retail
        row = self._add_row(pid, label, 1, retail, company_id, float(trade or retail), discount, 0.0)
        self._focus_items_cell(row, 1)
        return row


    def _add_row(self, prod_id, prod_name, qty, retail_price, company_id=0, trade_price=0.0, discount_pct=0.0, extra_pct=0.0):
        r = self.items_table.rowCount()
        self.items_table.insertRow(r)
        prod_item = QtWidgets.QTableWidgetItem(prod_name)
        prod_item.setData(QtCore.Qt.UserRole, {"product_id": int(prod_id), "company_id": int(company_id or 0)})
        prod_item.setFlags(prod_item.flags() & ~QtCore.Qt.ItemIsEditable)
        prod_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        self.items_table.setItem(r, 0, prod_item)
        retail_spin = self._make_money_spin(retail_price)
        self.items_table.setCellWidget(r, 1, retail_spin)
        pct_spin = self._make_pct_spin(discount_pct)
        extra_spin = self._make_pct_spin(extra_pct)
        qty_spin = self._make_qty_spin(qty)
        trade_item = QtWidgets.QTableWidgetItem(f"{float(trade_price or retail_price):.2f}")
        trade_item.setFlags(trade_item.flags() & ~QtCore.Qt.ItemIsEditable)
        trade_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
        self.items_table.setCellWidget(r, 2, pct_spin)
        self.items_table.setItem(r, 3, trade_item)
        self.items_table.setCellWidget(r, 4, extra_spin)
        self.items_table.setCellWidget(r, 5, qty_spin)
        line_total_item = QtWidgets.QTableWidgetItem("0.00")
        line_total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
        self.items_table.setItem(r, 6, line_total_item)

        for col in (1, 2, 4, 5):
            widget = self.items_table.cellWidget(r, col)
            if widget:
                widget.valueChanged.connect(lambda _=None, w=widget: self._on_widget_changed(w))
                widget.installEventFilter(self)
                try:
                    le = widget.lineEdit() if hasattr(widget, "lineEdit") else None
                except Exception:
                    le = None
                if le is not None:
                    le.installEventFilter(self)
        self._recalc_row(r)
        self._recalc_total()
        self._focus_items_cell(r, 2)
        return r

    def _on_widget_changed(self, widget):
        row = self._find_row_for_widget(widget)
        if row is None:
            return
        self._recalc_row(row)
        self._recalc_total()

    def _find_row_for_widget(self, widget):
        for r in range(self.items_table.rowCount()):
            for c in (1, 2, 4, 5):
                if self.items_table.cellWidget(r, c) is widget:
                    return r
        return None

    def _find_row_for_product(self, pid: int):
        for r in range(self.items_table.rowCount()):
            try:
                meta = self.items_table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                if int(meta.get("product_id", 0) or 0) == pid:
                    return r
            except Exception:
                pass
        return None

    def _recalc_row(self, row):
        try:
            retail = float(self.items_table.cellWidget(row, 1).value())
            pct = float(self.items_table.cellWidget(row, 2).value())
            extra = float(self.items_table.cellWidget(row, 4).value())
            qty = int(self.items_table.cellWidget(row, 5).value())
            trade = retail * (1.0 - (pct / 100.0))
            final = trade * (1.0 - (extra / 100.0))
            self._suppress_item_change = True
            self.items_table.item(row, 3).setText(f"{trade:.2f}")
            self._suppress_item_change = False
            self.items_table.item(row, 6).setText(f"{final * qty:.2f}")
        except Exception:
            pass

    def _recalc_total(self):
        total = 0.0
        for r in range(self.items_table.rowCount()):
            try:
                total += float(self.items_table.item(r, 6).text())
            except Exception:
                pass
        try:
            paid = max(0.0, float(self.paid_input.value()))
        except Exception:
            paid = 0.0
        due = max(0.0, float(total) - float(paid))
        self.total_label.setText(f"Total: {total:.2f}")
        self.due_label.setText(f"Due: {due:.2f}")
        if due > 1e-9:
            self.due_label.setStyleSheet("color: #F87171; font-weight: 700;")
        else:
            self.due_label.setStyleSheet("")

    def _focus_items_cell(self, row: int, col: int):
        if row is None or col is None:
            return
        self.items_table.setCurrentCell(row, col)
        w = self.items_table.cellWidget(row, col)
        if w:
            w.setFocus()
            if hasattr(w, "lineEdit") and w.lineEdit():
                try:
                    w.lineEdit().selectAll()
                except Exception:
                    pass

    def _editable_cols_for_row(self, row: int):
        return [1, 2, 4, 5]  # retail, discount, addl %, qty

    def _item_widget_position(self, obj):
        for r in range(self.items_table.rowCount()):
            for c in (1, 2, 4, 5):
                w = self.items_table.cellWidget(r, c)
                if w is None:
                    continue
                if obj is w:
                    return r, c
                try:
                    le = w.lineEdit() if hasattr(w, "lineEdit") else None
                except Exception:
                    le = None
                if le is not None and obj is le:
                    return r, c
        return None, None

    def _focus_items_from_search(self):
        if self.items_table.rowCount() <= 0:
            return
        row = self.items_table.currentRow()
        if row < 0 or row >= self.items_table.rowCount():
            row = self.items_table.rowCount() - 1
        editable_cols = self._editable_cols_for_row(row)
        target_col = 2 if 2 in editable_cols else editable_cols[0]
        self._focus_items_cell(row, target_col)

    def _remove_item(self):
        r = self.items_table.currentRow()
        if r < 0:
            focus_w = self.focusWidget()
            focus_row, _ = self._item_widget_position(focus_w)
            r = focus_row if focus_row is not None else -1
        if r >= 0:
            self.items_table.removeRow(r)
            if self.items_table.rowCount() > 0:
                next_row = min(r, self.items_table.rowCount() - 1)
                self._focus_items_cell(next_row, 2)
            self._recalc_total()

    def _clear_items(self):
        self.items_table.setRowCount(0)
        if hasattr(self, "paid_input"):
            self.paid_input.setValue(0.0)
        self._recalc_total()

    def _save_purchase(self):
        try:
            sid = int(self.supplier_cb.currentData() or 0)
        except Exception:
            sid = 0
        sname = (self.supplier_cb.currentText() or "").strip()
        if sname.lower() == "select or type name":
            sname = ""
        if sid <= 0 and not sname:
            QtWidgets.QMessageBox.information(self, "Supplier required", "Select or type a supplier before saving.")
            return
        rows = []
        total = 0.0
        for r in range(self.items_table.rowCount()):
            try:
                prod_item = self.items_table.item(r, 0)
                meta = prod_item.data(QtCore.Qt.UserRole) or {}
                pid = int(meta.get("product_id", 0) if isinstance(meta, dict) else meta)
                company_id = int(meta.get("company_id", 0) if isinstance(meta, dict) else 0)
                retail = float(self.items_table.cellWidget(r, 1).value())
                pct = float(self.items_table.cellWidget(r, 2).value())
                extra = float(self.items_table.cellWidget(r, 4).value())
                qty = int(self.items_table.cellWidget(r, 5).value())
                trade = retail * (1.0 - (pct / 100.0))
                final = trade * (1.0 - (extra / 100.0))
                rows.append(
                    {
                        "product_id": pid,
                        "company_id": company_id,
                        "quantity": qty,
                        "price": final,
                        "retail_price": retail,
                        "discount_pct": pct,
                        "extra_discount_pct": extra,
                        "trade_price": trade,
                    }
                )
                total += qty * final
            except Exception:
                pass
        if not rows:
            QtWidgets.QMessageBox.information(self, "No Items", "Add at least one item.")
            return
        try:
            paid = max(0.0, float(self.paid_input.value()))
        except Exception:
            paid = 0.0
        if paid - total > 1e-6:
            QtWidgets.QMessageBox.information(self, "Invalid Payment", "Paid amount cannot exceed purchase total.")
            return
        try:
            if sid == 0 and sname:
                created = self.api.supplier_upsert({"name": sname})
                if isinstance(created, dict) and created.get("detail"):
                    raise Exception(str(created.get("detail")))
                try:
                    sid = int((created or {}).get("id", 0) or 0)
                except Exception:
                    sid = 0
            payload = {
                "supplier_id": int(sid or 0),
                "supplier_name": sname,
                "total": total,
                "paid": paid,
                "items": rows,
            }
            if getattr(self, "_edit_purchase_id", None):
                self.api.purchase_update(int(self._edit_purchase_id), payload)
                QtWidgets.QMessageBox.information(self, "Saved", "Purchase updated")
            else:
                self.api.purchase_new(payload)
                QtWidgets.QMessageBox.information(self, "Saved", "Purchase saved")
            self._clear_items()
            self._exit_edit_mode()
            self.refresh_history()
            self.inventory_changed.emit()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def refresh_history(self):
        try:
            data = self.api.purchases_page(
                page=self._history_page,
                page_size=25,
            )
            docs = data.get("items", []) or []
            self._history_pages = int(data.get("pages", 1) or 1)
            self._history_page = max(
                1,
                min(int(data.get("page", self._history_page) or self._history_page), self._history_pages),
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.history_table.setRowCount(0)
        for p in docs or []:
            r = self.history_table.rowCount()
            self.history_table.insertRow(r)
            raw_dt = p.get("date", "")
            date_txt, time_txt = self._split_datetime_text(raw_dt)
            id_item = QtWidgets.QTableWidgetItem(str(p.get("id", "")))
            date_item = QtWidgets.QTableWidgetItem(date_txt)
            time_item = QtWidgets.QTableWidgetItem(time_txt)
            supplier_item = QtWidgets.QTableWidgetItem(p.get("supplier_name", ""))
            items = p.get("items") or []
            items_item = QtWidgets.QTableWidgetItem(str(len(items)))
            total_item = QtWidgets.QTableWidgetItem(f"{float(p.get('total', 0.0)):.2f}")

            date_item.setTextAlignment(QtCore.Qt.AlignCenter)
            time_item.setTextAlignment(QtCore.Qt.AlignCenter)
            items_item.setTextAlignment(QtCore.Qt.AlignCenter)
            total_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

            self.history_table.setItem(r, 0, id_item)
            self.history_table.setItem(r, 1, date_item)
            self.history_table.setItem(r, 2, time_item)
            self.history_table.setItem(r, 3, supplier_item)
            self.history_table.setItem(r, 4, items_item)
            self.history_table.setItem(r, 5, total_item)
        self.history_page_label.setText(f"Page {self._history_page} / {self._history_pages}")
        self.history_btn_prev.setEnabled(self._history_page > 1)
        self.history_btn_next.setEnabled(self._history_page < self._history_pages)

    def _split_datetime_text(self, raw_value):
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

    def _edit_selected(self):
        r = self.history_table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a purchase row first")
            return
        pid_item = self.history_table.item(r, 0)
        if not pid_item:
            return
        try:
            pid = int(pid_item.text())
        except Exception:
            return
        match = self.api.purchase_get(pid)
        if isinstance(match, dict) and match.get("detail"):
            QtWidgets.QMessageBox.information(self, "Not Found", "Could not locate purchase to edit")
            return
        self._load_purchase_into_form(match)

    def _delete_selected(self):
        if not self._can_edit_invoice:
            QtWidgets.QMessageBox.information(
                self,
                "Permission",
                "You do not have permission to delete purchase invoices.",
            )
            return
        r = self.history_table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a purchase row first")
            return
        pid_item = self.history_table.item(r, 0)
        if not pid_item:
            return
        try:
            pid = int(pid_item.text())
        except Exception:
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this purchase?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            resp = self.api.purchase_delete(pid, user_id=int(self.user_id or 0))
            if isinstance(resp, dict) and str(resp.get("detail", "")).strip():
                QtWidgets.QMessageBox.information(self, "Delete blocked", str(resp.get("detail", "")).strip())
                return
            QtWidgets.QMessageBox.information(self, "Deleted", "Purchase deleted")
            self.refresh_history()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _load_purchase_into_form(self, purchase: dict):
        self._edit_purchase_id = int(purchase.get("id", 0) or 0)
        self.btn_save.setText("Update Purchase")
        self.btn_cancel_edit.setVisible(True)
        self.tabs.setCurrentIndex(0)
        self._load_suppliers()
        sid = int(purchase.get("supplier_id", 0) or 0)
        sname = purchase.get("supplier_name", "")
        if sid:
            idx = self.supplier_cb.findData(sid)
            if idx >= 0:
                self.supplier_cb.setCurrentIndex(idx)
            else:
                self.supplier_cb.setCurrentText(sname)
        else:
            self.supplier_cb.setCurrentText(sname)
        self._clear_items()
        products = self._load_products(force=True)
        for it in purchase.get("items", []) or []:
            pid = int(it.get("product_id", 0) or 0)
            company_id = int(it.get("company_id", 0) or 0)
            prod = next((p for p in products if int(p.get("id")) == pid), None)
            name = prod.get("name", f"ID {pid}") if prod else f"ID {pid}"
            retail_val = it.get("retail_price")
            if retail_val is None:
                retail_val = it.get("price", 0.0)
            discount_val = it.get("discount_pct")
            extra_val = it.get("extra_discount_pct")
            retail = float(retail_val or 0.0)
            discount_pct = float(discount_val or 0.0)
            extra_pct = float(extra_val or 0.0)
            qty = int(it.get("quantity", 1) or 1)
            trade = it.get("trade_price")
            if company_id == 0 and prod:
                company_id = int(prod.get("company_id", 0) or 0)
            base_price = float(trade or it.get("price", 0.0) or 0.0)
            self._add_row(pid, name, qty, retail, company_id, base_price, discount_pct, extra_pct)
        try:
            self.paid_input.setValue(max(0.0, float(purchase.get("paid", 0.0) or 0.0)))
        except Exception:
            self.paid_input.setValue(0.0)
        self._recalc_total()

    def _exit_edit_mode(self):
        self._edit_purchase_id = None
        self.btn_save.setText("Save Purchase")
        self.btn_cancel_edit.setVisible(False)

    def _cancel_edit(self):
        if QtWidgets.QMessageBox.question(self, "Cancel Edit", "Discard changes?") != QtWidgets.QMessageBox.Yes:
            return
        self._clear_items()
        self._exit_edit_mode()

    # ---------- Keyboard navigation ----------
    def eventFilter(self, obj, event):
        search_w = getattr(self, "search", None)
        results_w = getattr(self, "results", None)
        items_table = getattr(self, "items_table", None)
        if obj is search_w and event.type() == QtCore.QEvent.FocusOut:
            QtCore.QTimer.singleShot(120, self._hide_results_popup)
        if obj is items_table and event.type() == QtCore.QEvent.MouseButtonPress:
            self._hide_results_popup()
        if obj is results_w and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Escape:
                self._hide_results_popup()
                return True
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            table = items_table
            search = search_w
            if obj is search:
                if key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                    if self.results.isVisible() and self.results.count() > 0:
                        row = self.results.currentRow()
                        if row < 0:
                            row = 0
                        if key == QtCore.Qt.Key_Up:
                            row = max(0, row - 1)
                        else:
                            row = min(self.results.count() - 1, row + 1)
                        self.results.setCurrentRow(row)
                        return True
                    if key == QtCore.Qt.Key_Down and table is not None and table.rowCount() > 0:
                        self._focus_items_from_search()
                        return True
                elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    if self.results.isVisible() and self.results.currentItem():
                        self._add_first_search_result()
                        return True
                    if table is not None and table.rowCount() > 0:
                        self._focus_items_from_search()
                        return True
                elif key == QtCore.Qt.Key_Right:
                    if table is not None and table.rowCount() > 0:
                        self._focus_items_from_search()
                        return True
            elif obj is table:
                if key == QtCore.Qt.Key_Up:
                    self._move_item_row(-1)
                    return True
                if key == QtCore.Qt.Key_Down:
                    self._move_item_row(1)
                    return True
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    self._focus_next_item_field()
                    return True
                if key == QtCore.Qt.Key_Left:
                    self._focus_prev_item_field()
                    return True
                if key == QtCore.Qt.Key_Right:
                    self._focus_next_item_field()
                    return True
                if key == QtCore.Qt.Key_Delete:
                    self._remove_item()
                    return True
            else:
                row, col = self._item_widget_position(obj)
                if row is not None and col is not None:
                    self.items_table.setCurrentCell(row, col)
                    if key == QtCore.Qt.Key_Delete:
                        self._remove_item()
                        return True
                    if key == QtCore.Qt.Key_Left:
                        self._focus_prev_item_field()
                        return True
                    if key == QtCore.Qt.Key_Right:
                        self._focus_next_item_field()
                        return True
                    if key == QtCore.Qt.Key_Up:
                        self._move_item_row(-1, col)
                        return True
                    if key == QtCore.Qt.Key_Down:
                        self._move_item_row(1, col)
                        return True
                    if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                        self._focus_next_item_field()
                        return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.results.isVisible():
            self._position_results_popup()

    def _focus_next_item_field(self):
        if self.items_table.rowCount() == 0:
            return
        row = self.items_table.currentRow()
        if row < 0:
            row = 0
        editable_cols = self._editable_cols_for_row(row)
        col = self.items_table.currentColumn()
        focus_w = self.focusWidget()
        for c in editable_cols:
            w = self.items_table.cellWidget(row, c)
            if w is focus_w:
                col = c
                break
            try:
                le = w.lineEdit() if (w is not None and hasattr(w, "lineEdit")) else None
            except Exception:
                le = None
            if le is focus_w:
                col = c
                break
        try:
            idx = editable_cols.index(col)
        except ValueError:
            idx = -1
        # At end of row
        if idx == len(editable_cols) - 1:
            if row + 1 < self.items_table.rowCount():
                next_cols = self._editable_cols_for_row(row + 1)
                self._focus_items_cell(row + 1, next_cols[0])
            else:
                self._focus_search()
            return
        if idx + 1 < len(editable_cols):
            next_row, next_col = row, editable_cols[idx + 1]
        else:
            next_row, next_col = row + 1, editable_cols[0]
        if next_row >= self.items_table.rowCount():
            next_row = row
        self._focus_items_cell(next_row, next_col)

    def _focus_prev_item_field(self):
        if self.items_table.rowCount() == 0:
            return
        row = self.items_table.currentRow()
        if row < 0:
            row = 0
        editable_cols = self._editable_cols_for_row(row)
        col = self.items_table.currentColumn()
        focus_w = self.focusWidget()
        for c in editable_cols:
            w = self.items_table.cellWidget(row, c)
            if w is focus_w:
                col = c
                break
            try:
                le = w.lineEdit() if (w is not None and hasattr(w, "lineEdit")) else None
            except Exception:
                le = None
            if le is focus_w:
                col = c
                break
        try:
            idx = editable_cols.index(col)
        except ValueError:
            idx = 0
        if idx <= 0:
            if row - 1 >= 0:
                prev_cols = self._editable_cols_for_row(row - 1)
                self._focus_items_cell(row - 1, prev_cols[-1])
            else:
                self._focus_search()
            return
        self._focus_items_cell(row, editable_cols[idx - 1])

    def _move_item_row(self, delta: int, preferred_col: int | None = None):
        if self.items_table.rowCount() <= 0:
            return
        row = self.items_table.currentRow()
        if row < 0:
            row = 0
        col = self.items_table.currentColumn()
        if preferred_col is not None:
            col = preferred_col
        if col not in (1, 2, 4, 5):
            col = 2
        new_row = max(0, min(self.items_table.rowCount() - 1, row + delta))
        self._focus_items_cell(new_row, col)
