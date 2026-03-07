from PyQt5 import QtWidgets, QtPrintSupport, QtCore, QtGui
from pathlib import Path
from datetime import datetime
from .ui_common import (
    apply_form_layout,
    apply_header_layout,
    apply_page_layout,
    configure_table,
    dialog_screen_limits,
    fit_dialog_to_contents,
    polish_controls,
    set_accent,
    set_danger,
    set_secondary,
)


class POSView(QtWidgets.QWidget):
    """Point of Sale view redesigned for speed and simplicity.

    Key improvements:
    - Always-visible search box with instant results (Enter to add)
    - Clean cart table: Item, Qty, Price, Line Total, Remove
    - Big checkout area with Subtotal, Discount %, VAT, Total
    - Clear Cart and keyboard shortcuts (F2 focus search, Del remove)
    """

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user_id = 0
        self.products_cache = []
        self.held_sales: list[dict] = []
        self._load_held_sales()
        self.vat_percent = 0.0
        self._edit_transaction_id = None
        self._edit_original_qty_by_product: dict[int, int] = {}
        self._edit_existing_paid = 0.0
        self._build()
        self._load_customers()
        self._load_products_cache()
        self._load_settings()

    # ---------- UI ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        apply_page_layout(root)

        # Top card: sale controls + quick search
        top_card = QtWidgets.QFrame()
        top_card.setObjectName("posTopCard")
        top_wrap = QtWidgets.QVBoxLayout(top_card)
        top_wrap.setContentsMargins(12, 10, 12, 10)
        top_wrap.setSpacing(8)

        # Customer + invoice row
        top = QtWidgets.QHBoxLayout()
        apply_header_layout(top)
        top.setSpacing(8)
        cust_lbl = QtWidgets.QLabel("Customer:")
        cust_lbl.setObjectName("mutedLabel")
        top.addWidget(cust_lbl)
        self.customer = QtWidgets.QComboBox()
        self.customer.setObjectName("posCustomerField")
        self.customer.setMinimumWidth(300)
        self.customer.setMinimumHeight(36)
        self.customer.setEditable(True)
        self.customer.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.customer.setMaxVisibleItems(20)
        cust_line = self.customer.lineEdit()
        if cust_line is not None:
            cust_line.setObjectName("posCustomerInput")
            cust_line.setPlaceholderText("Type to search customer...")
            cust_line.returnPressed.connect(self._select_customer_by_typed_text)
        try:
            self.customer.view().setObjectName("searchResultsPopup")
        except Exception:
            pass
        comp = self.customer.completer()
        if comp is not None:
            comp.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            comp.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            try:
                comp.setFilterMode(QtCore.Qt.MatchContains)
            except Exception:
                pass
            try:
                comp.popup().setObjectName("searchResultsPopup")
            except Exception:
                pass
        top.addWidget(self.customer)
        top.addStretch(1)
        inv_lbl = QtWidgets.QLabel("Invoice #:")
        inv_lbl.setObjectName("mutedLabel")
        top.addWidget(inv_lbl)
        self.invoice_no = QtWidgets.QLineEdit()
        self.invoice_no.setObjectName("invoiceInput")
        self.invoice_no.setPlaceholderText("e.g. 1001")
        self.invoice_no.setMinimumWidth(190)
        self.invoice_no.setMinimumHeight(36)
        self.invoice_no.textChanged.connect(lambda _t: self._update_payment_history_visibility())
        self.invoice_no.returnPressed.connect(self._reopen_invoice_by_number)
        top.addWidget(self.invoice_no)
        self.payment_history_btn = QtWidgets.QPushButton("Payments")
        set_secondary(self.payment_history_btn)
        self.payment_history_btn.clicked.connect(self._show_invoice_payments)
        self.payment_history_btn.setVisible(False)
        top.addWidget(self.payment_history_btn)
        self.cancel_invoice_edit_btn = QtWidgets.QPushButton("Cancel Edit")
        set_danger(self.cancel_invoice_edit_btn)
        self.cancel_invoice_edit_btn.clicked.connect(self._cancel_invoice_edit)
        self.cancel_invoice_edit_btn.setVisible(False)
        top.addWidget(self.cancel_invoice_edit_btn)
        top_wrap.addLayout(top)

        # Search row
        search_row = QtWidgets.QHBoxLayout()
        apply_header_layout(search_row)
        search_row.setSpacing(8)
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("mainSearchInput")
        self.search.setPlaceholderText("Search product by name, company, or ID...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search_changed)
        self.search.returnPressed.connect(self._add_first_search_result)
        self.search.setMinimumHeight(40)
        search_row.addWidget(self.search, 1)
        top_wrap.addLayout(search_row)
        root.addWidget(top_card)

        # Search results list (inline, collapsible)
        self.results = QtWidgets.QListWidget(self)
        self.results.setObjectName("searchResultsPopup")
        self.results.setVisible(False)
        self.results.setMaximumHeight(260)
        self.results.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.results.itemActivated.connect(self._on_result_activate)
        self.results.installEventFilter(self)

        # Cart table (match Purchases columns)
        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setObjectName("posCartTable")
        self.table.setHorizontalHeaderLabels([
            "Product", "Retail", "% Discount", "Trade", "Addl %", "Qty", "Line Total", "Margin Tag",
        ])
        configure_table(self.table, stretch_last=False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        table_font = self.table.font()
        table_font.setPointSize(max(10, table_font.pointSize()))
        self.table.setFont(table_font)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        col_widths = {
            1: 132,  # Retail
            2: 102,  # % Discount
            3: 132,  # Trade
            4: 102,  # Addl %
            5: 92,   # Qty
            6: 152,  # Line Total
            7: 148,  # Margin Tag
        }
        for col, width in col_widths.items():
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        root.addWidget(self.table, 1)

        # Bottom: totals + actions
        bottom = QtWidgets.QHBoxLayout()
        apply_header_layout(bottom)
        bottom.setSpacing(8)
        self.clear_btn = QtWidgets.QPushButton("Clear Cart")
        self.clear_btn.setObjectName("posActionBtn")
        set_secondary(self.clear_btn)
        self.clear_btn.clicked.connect(self._clear_cart)
        bottom.addWidget(self.clear_btn)
        self.hold_btn = QtWidgets.QPushButton("Hold Sale")
        self.hold_btn.setObjectName("posActionBtn")
        set_secondary(self.hold_btn)
        self.hold_btn.clicked.connect(self._hold_sale)
        bottom.addWidget(self.hold_btn)
        self.resume_btn = QtWidgets.QPushButton("Resume Sale")
        self.resume_btn.setObjectName("posActionBtn")
        set_secondary(self.resume_btn)
        self.resume_btn.clicked.connect(self._resume_sale)
        bottom.addWidget(self.resume_btn)
        bottom.addStretch(1)

        self.discount = QtWidgets.QDoubleSpinBox()
        self.discount.setRange(0, 100)
        self.discount.setDecimals(2)
        self.discount.setSingleStep(1.0)
        self.discount.setMinimumWidth(110)
        self.discount.valueChanged.connect(self._recalc_totals)
        self.discount.installEventFilter(self)
        try:
            discount_le = self.discount.lineEdit()
        except Exception:
            discount_le = None
        if discount_le is not None:
            discount_le.installEventFilter(self)

        sale_box = QtWidgets.QGroupBox("Sale")
        sale_box.setObjectName("totalsCard")
        sale_box.setMinimumWidth(260)
        sale_layout = QtWidgets.QGridLayout(sale_box)
        sale_layout.setContentsMargins(10, 8, 10, 8)
        sale_layout.setHorizontalSpacing(10)
        sale_layout.setVerticalSpacing(6)
        sale_layout.setColumnStretch(1, 1)

        totals_box = QtWidgets.QGroupBox("Totals")
        totals_box.setObjectName("totalsCard")
        totals_box.setMinimumWidth(250)
        totals_layout = QtWidgets.QFormLayout(totals_box)
        apply_form_layout(totals_layout)
        totals_layout.setVerticalSpacing(4)
        self.subtotal_label = QtWidgets.QLabel("0.00")
        self.vat_label = QtWidgets.QLabel("0.00")
        self.total_label = QtWidgets.QLabel("0.00")
        self.total_label.setObjectName("moneyStrong")
        self.paid_spin = QtWidgets.QDoubleSpinBox()
        self.paid_spin.setRange(0, 10**9)
        self.paid_spin.setDecimals(2)
        self.paid_spin.setValue(0.0)
        self.paid_spin.setSingleStep(10.0)
        self.paid_spin.valueChanged.connect(self._recalc_totals)
        self.paid_spin.installEventFilter(self)
        try:
            paid_le = self.paid_spin.lineEdit()
        except Exception:
            paid_le = None
        if paid_le is not None:
            paid_le.installEventFilter(self)
        self.paid_input_label = QtWidgets.QLabel("Paid:")
        self.paid_prior_key_label = QtWidgets.QLabel("Paid So Far:")
        self.paid_prior_value_label = QtWidgets.QLabel("0.00")
        self.paid_total_key_label = QtWidgets.QLabel("Paid Total:")
        self.paid_total_value_label = QtWidgets.QLabel("0.00")
        self.due_label = QtWidgets.QLabel("0.00")
        self.discount_key_label = QtWidgets.QLabel("Discount %:")
        for key_lbl in (
            self.discount_key_label,
            self.paid_input_label,
            self.paid_prior_key_label,
            self.paid_total_key_label,
        ):
            key_lbl.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        font_bold = self.total_label.font()
        font_bold.setPointSize(font_bold.pointSize() + 1)
        font_bold.setBold(True)
        self.total_label.setFont(font_bold)
        self.discount.setMinimumHeight(28)
        self.paid_spin.setMinimumHeight(28)
        sale_layout.addWidget(self.discount_key_label, 0, 0)
        sale_layout.addWidget(self.discount, 0, 1)
        sale_layout.addWidget(self.paid_input_label, 1, 0)
        sale_layout.addWidget(self.paid_spin, 1, 1)
        sale_layout.addWidget(self.paid_prior_key_label, 2, 0)
        sale_layout.addWidget(self.paid_prior_value_label, 2, 1)
        sale_layout.addWidget(self.paid_total_key_label, 3, 0)
        sale_layout.addWidget(self.paid_total_value_label, 3, 1)

        totals_layout.addRow("Subtotal:", self.subtotal_label)
        totals_layout.addRow("VAT:", self.vat_label)
        totals_layout.addRow("Total:", self.total_label)
        totals_layout.addRow("Due:", self.due_label)
        self.paid_prior_key_label.setVisible(False)
        self.paid_prior_value_label.setVisible(False)
        self.paid_total_key_label.setVisible(False)
        self.paid_total_value_label.setVisible(False)
        bottom.addWidget(sale_box)
        bottom.addWidget(totals_box)

        self.checkout_btn = QtWidgets.QPushButton("Checkout")
        self.checkout_btn.setObjectName("checkoutBtn")
        set_accent(self.checkout_btn)
        self.checkout_btn.clicked.connect(self.checkout)
        bottom.addWidget(self.checkout_btn, 0, QtCore.Qt.AlignBottom)
        self._sync_sale_label_widths()
        self._sync_checkout_button_caption()
        root.addLayout(bottom)

        # Shortcuts
        QtWidgets.QShortcut(QtGui.QKeySequence("F2"), self, activated=self._focus_search)
        QtWidgets.QShortcut(QtGui.QKeySequence("F8"), self, activated=self._show_purchase_history)
        QtWidgets.QShortcut(QtGui.QKeySequence("F9"), self, activated=self._show_sales_history)
        QtWidgets.QShortcut(QtGui.QKeySequence("F11"), self, activated=self._hold_sale)
        QtWidgets.QShortcut(QtGui.QKeySequence("F12"), self, activated=self._resume_sale)
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self, activated=self._remove_selected_row)
        # Keyboard-only navigation helpers
        self.search.installEventFilter(self)
        self.table.installEventFilter(self)
        polish_controls(self)

    # ---------- Data loads ----------
    def _load_products_cache(self):
        try:
            def _fetch():
                return self.api.products() or []
            self.products_cache = self._with_loader("Loading products...", _fetch) or []
        except Exception as e:
            self.products_cache = []
            QtWidgets.QMessageBox.warning(self, "Products", str(e))
        self._on_search_changed(self.search.text())

    def _load_settings(self):
        try:
            s = self.api.settings_map() or {}
            self.vat_percent = float((s.get("settings", {}) or {}).get("vat_percent", 0.0))
        except Exception:
            self.vat_percent = 0.0
        self._recalc_totals()

    def refresh(self):
        # Called when user enters POS from sidebar.
        try:
            self.products_cache = self.api.products() or []
        except Exception:
            self.products_cache = []
        try:
            self._load_customers()
        except Exception:
            pass
        self._on_search_changed(self.search.text())

    def _load_customers(self):
        prev_id = 0
        try:
            prev_id = int(self.customer.currentData() or 0)
        except Exception:
            prev_id = 0
        try:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)
            customers = self.api.customers() or []
            customers = sorted(customers, key=lambda x: str((x or {}).get("name", "")).lower())
            for c in customers:
                self.customer.addItem(c.get("name", "Customer"), int(c.get("id")))
        except Exception:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)
        if prev_id > 0:
            idx = self.customer.findData(prev_id)
            if idx >= 0:
                self.customer.setCurrentIndex(idx)
            else:
                self.customer.setCurrentIndex(0)
        else:
            self.customer.setCurrentIndex(0)

    def _select_customer_by_typed_text(self):
        text = (self.customer.currentText() or "").strip().lower()
        if not text:
            self._focus_search()
            return
        # Prefer exact match first
        for i in range(self.customer.count()):
            if (self.customer.itemText(i) or "").strip().lower() == text:
                self.customer.setCurrentIndex(i)
                self._focus_search()
                return
        # Fallback to first contains match
        for i in range(self.customer.count()):
            if text in (self.customer.itemText(i) or "").strip().lower():
                self.customer.setCurrentIndex(i)
                self._focus_search()
                return
        self._focus_search()

    # ---------- Invoice edit mode ----------
    def _update_payment_history_visibility(self):
        show = self._edit_transaction_id is not None
        self.payment_history_btn.setVisible(show)

    def _set_invoice_edit_mode(self, transaction_id: int, original_qty_map: dict[int, int], existing_paid: float = 0.0):
        self._edit_transaction_id = int(transaction_id)
        self._edit_original_qty_by_product = {
            int(pid): int(qty)
            for pid, qty in (original_qty_map or {}).items()
            if int(pid) > 0 and int(qty) > 0
        }
        try:
            self._edit_existing_paid = max(0.0, float(existing_paid or 0.0))
        except Exception:
            self._edit_existing_paid = 0.0
        self._sync_checkout_button_caption()
        self.cancel_invoice_edit_btn.setVisible(True)
        self.paid_input_label.setText("Add Payment:")
        self.paid_prior_key_label.setVisible(True)
        self.paid_prior_value_label.setVisible(True)
        self.paid_total_key_label.setVisible(True)
        self.paid_total_value_label.setVisible(True)
        self._sync_sale_label_widths()
        self.paid_spin.setValue(0.0)
        self._recalc_totals()
        self._update_payment_history_visibility()

    def _exit_invoice_edit_mode(self):
        self._edit_transaction_id = None
        self._edit_original_qty_by_product = {}
        self._edit_existing_paid = 0.0
        self._sync_checkout_button_caption()
        self.cancel_invoice_edit_btn.setVisible(False)
        self.paid_input_label.setText("Paid:")
        self.paid_prior_key_label.setVisible(False)
        self.paid_prior_value_label.setVisible(False)
        self.paid_total_key_label.setVisible(False)
        self.paid_total_value_label.setVisible(False)
        self._sync_sale_label_widths()
        self.invoice_no.clear()
        self._update_payment_history_visibility()

    def _sync_sale_label_widths(self):
        labels = [
            self.discount_key_label,
            self.paid_input_label,
            self.paid_prior_key_label,
            self.paid_total_key_label,
        ]
        visible = [lbl for lbl in labels if not lbl.isHidden()]
        if not visible:
            return
        needed = max(lbl.fontMetrics().horizontalAdvance(lbl.text()) for lbl in visible) + 10
        target_width = max(80, min(156, needed))
        for lbl in labels:
            lbl.setMinimumWidth(target_width)

    def _sync_checkout_button_caption(self):
        fm = self.checkout_btn.fontMetrics()
        if self._edit_transaction_id is None:
            text = "Checkout"
            self.checkout_btn.setText(text)
            self.checkout_btn.setToolTip("")
            self.checkout_btn.setMinimumWidth(max(136, fm.horizontalAdvance(text) + 40))
            return

        full_text = f"Update Invoice #{self._edit_transaction_id}"
        # Keep a compact caption to avoid clipping in non-maximized windows.
        text = "Update Invoice"
        self.checkout_btn.setText(text)
        self.checkout_btn.setToolTip(full_text)
        self.checkout_btn.setMinimumWidth(max(136, fm.horizontalAdvance(text) + 40))

    def _cancel_invoice_edit(self):
        if self._edit_transaction_id is None:
            return
        if QtWidgets.QMessageBox.question(
            self,
            "Cancel Edit",
            "Discard current invoice edits?",
        ) != QtWidgets.QMessageBox.Yes:
            return
        self._exit_invoice_edit_mode()
        self._clear_cart()

    # ---------- Search ----------
    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _focus_discount_input(self):
        self.discount.setFocus()
        try:
            le = self.discount.lineEdit()
        except Exception:
            le = None
        if le is not None:
            try:
                le.selectAll()
            except Exception:
                pass

    def _focus_paid_input(self):
        self.paid_spin.setFocus()
        try:
            le = self.paid_spin.lineEdit()
        except Exception:
            le = None
        if le is not None:
            try:
                le.selectAll()
            except Exception:
                pass

    def _position_results_popup(self):
        if self.results.count() <= 0:
            return
        row_h = self.results.sizeHintForRow(0)
        if row_h <= 0:
            row_h = 26
        visible_rows = min(max(1, self.results.count()), 8)
        popup_h = min(visible_rows * row_h + 8, 260)
        top_left = self.search.mapTo(self, QtCore.QPoint(0, self.search.height() + 4))
        popup_w = self.search.width()

        # Keep the popup within this view's vertical bounds.
        bottom_space = self.height() - top_left.y() - 10
        if bottom_space < popup_h:
            above_y = self.search.mapTo(self, QtCore.QPoint(0, -popup_h - 4)).y()
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

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QtCore.QEvent.FocusOut:
            QtCore.QTimer.singleShot(120, self._hide_results_popup)
        if obj is self.table and event.type() == QtCore.QEvent.MouseButtonPress:
            self._hide_results_popup()
        if obj is self.results and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Escape:
                self._hide_results_popup()
                return True
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            shift_enter = bool(event.modifiers() & QtCore.Qt.ShiftModifier) and key in (
                QtCore.Qt.Key_Return,
                QtCore.Qt.Key_Enter,
            )
            if obj is self.search:
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
                    # If no search results are open, Down moves into cart editing.
                    if key == QtCore.Qt.Key_Down and self.table.rowCount() > 0:
                        self._focus_cart_from_search()
                        return True
                elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    if self.results.isVisible() and self.results.currentItem():
                        self._add_first_search_result()
                        return True
                    # Enter in search (without an active result) jumps to cart fields.
                    if self.table.rowCount() > 0:
                        self._focus_cart_from_search()
                        return True
                elif key == QtCore.Qt.Key_Right:
                    if self.table.rowCount() > 0:
                        self._focus_cart_from_search()
                        return True
            elif obj is self.table:
                if shift_enter:
                    self._focus_discount_input()
                    return True
                if key == QtCore.Qt.Key_Delete:
                    self._remove_selected_row()
                    return True
                if key == QtCore.Qt.Key_Up:
                    self._move_cart_row(-1)
                    return True
                if key == QtCore.Qt.Key_Down:
                    self._move_cart_row(1)
                    return True
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    self._focus_next_cart_field()
                    return True
                if key == QtCore.Qt.Key_Left:
                    self._focus_prev_cart_field()
                    return True
                if key == QtCore.Qt.Key_Right:
                    self._focus_next_cart_field()
                    return True
            elif obj is self.discount or obj is self.discount.lineEdit():
                if shift_enter:
                    self._focus_paid_input()
                    return True
            elif obj is self.paid_spin or obj is self.paid_spin.lineEdit():
                if shift_enter:
                    self.checkout()
                    return True
            else:
                row, col = self._cart_widget_position(obj)
                if row is not None and col is not None:
                    self.table.setCurrentCell(row, col)
                    if key == QtCore.Qt.Key_Delete:
                        self._remove_row(row)
                        return True
                    if shift_enter:
                        self._focus_discount_input()
                        return True
                    if key == QtCore.Qt.Key_Left:
                        self._focus_prev_cart_field()
                        return True
                    if key == QtCore.Qt.Key_Right:
                        self._focus_next_cart_field()
                        return True
                    if key == QtCore.Qt.Key_Up:
                        self._move_cart_row(-1, col)
                        return True
                    if key == QtCore.Qt.Key_Down:
                        self._move_cart_row(1, col)
                        return True
                    if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                        self._focus_next_cart_field()
                        return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.results.isVisible():
            self._position_results_popup()
        self._sync_sale_label_widths()
        self._sync_checkout_button_caption()

    def _on_search_changed(self, text: str):
        text_raw = (text or "").strip()
        text_l = text_raw.lower()
        self.results.clear()
        # Ensure cache is loaded at least once
        if not self.products_cache:
            try:
                self.products_cache = self.api.products() or []
            except Exception:
                self.products_cache = []
        if not text_l:
            self._hide_results_popup()
            return
        count = 0
        is_digits = text_raw.isdigit()
        for p in self.products_cache:
            try:
                name = str(p.get("name", ""))
                company = str(p.get("company_name", ""))
                pid = str(p.get("id", ""))
                if (
                    text_l in name.lower()
                    or (company and text_l in company.lower())
                    or (is_digits and text_raw == pid)
                ):
                    label = f"{name} ({company})" if company else name
                    item = QtWidgets.QListWidgetItem(label)
                    item.setData(QtCore.Qt.UserRole, int(p.get("id")))
                    self.results.addItem(item)
                    count += 1
                    if count >= 100:  # cap list for responsiveness
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
        prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == pid), None)
        if not prod:
            return
        row = self._add_product_to_cart(prod)
        self.search.clear()
        self._hide_results_popup()
        if row is not None:
            self._focus_cart_cell(row, 2)

    def _selected_product_for_history(self):
        # Prefer selected cart row
        r = self.table.currentRow()
        if r >= 0:
            item = self.table.item(r, 0)
            if item:
                meta = item.data(QtCore.Qt.UserRole) or {}
                try:
                    pid = int(meta.get("id", 0) or 0)
                except Exception:
                    pid = 0
                if pid:
                    return pid, item.text()
        # Fallback to highlighted search result
        it = self.results.currentItem()
        if it is not None:
            try:
                pid = int(it.data(QtCore.Qt.UserRole) or 0)
            except Exception:
                pid = 0
            if pid:
                return pid, it.text()
        return None

    def _show_purchase_history(self):
        sel = self._selected_product_for_history()
        if not sel:
            QtWidgets.QMessageBox.information(
                self,
                "Select product",
                "Select a product in the cart or search results to view its purchase history.",
            )
            return
        pid, name = sel
        try:
            docs = self._with_loader("Loading purchase history...", self.api.purchases_list) or []
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        rows = []
        for p in docs:
            date = p.get("date", "")
            supplier = p.get("supplier_name", "")
            for it in p.get("items") or []:
                try:
                    if int(it.get("product_id", 0) or 0) != pid:
                        continue
                except Exception:
                    continue
                qty = int(it.get("quantity", 0) or 0)
                retail = it.get("retail_price", it.get("price", 0.0))
                trade = it.get("trade_price", it.get("price", 0.0))
                disc = it.get("discount_pct", None)
                extra = it.get("extra_discount_pct", None)
                try:
                    retail = float(retail or 0.0)
                except Exception:
                    retail = 0.0
                try:
                    trade = float(trade or 0.0)
                except Exception:
                    trade = 0.0
                try:
                    disc = float(disc) if disc is not None else None
                except Exception:
                    disc = None
                try:
                    extra = float(extra) if extra is not None else None
                except Exception:
                    extra = None
                try:
                    final = float(it.get("price", trade) or 0.0)
                except Exception:
                    final = trade
                rows.append(
                    {
                        "date": date,
                        "supplier": supplier,
                        "qty": qty,
                        "retail": retail,
                        "trade": trade,
                        "disc": disc,
                        "extra": extra,
                        "final": final,
                    }
                )
        if not rows:
            QtWidgets.QMessageBox.information(self, "No history", "No purchases found for this product.")
            return
        rows.sort(key=lambda r: r.get("date", ""), reverse=True)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            max_dlg_w = int(geo.width() * 0.92)
            max_dlg_h = int(geo.height() * 0.90)
        else:
            max_dlg_w = 1180
            max_dlg_h = 760

        row_h = 32
        header_h = 34
        chrome_h = 180  # title + optional note + buttons + margins
        max_rows_fit = max(1, int((max_dlg_h - chrome_h - header_h) / max(1, row_h)))
        visible_rows = rows[:max_rows_fit]
        hidden_count = max(0, len(rows) - len(visible_rows))

        def _date_only_text(raw_value):
            dt = str(raw_value or "").strip()
            if not dt:
                return ""
            try:
                parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                return parsed.strftime("%d-%m-%Y")
            except Exception:
                normalized = dt.replace("T", " ")
                parts = normalized.split()
                date_txt = parts[0] if parts else normalized
                try:
                    return datetime.strptime(date_txt, "%Y-%m-%d").strftime("%d-%m-%Y")
                except Exception:
                    return date_txt

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Purchases for {name}")
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        v.addWidget(QtWidgets.QLabel(f"Recent purchases for {name}"))
        table = QtWidgets.QTableWidget(len(visible_rows), 8)
        table.setHorizontalHeaderLabels(
            ["Date", "Supplier", "Qty", "Retail", "Trade", "%Disc", "Addl %", "Line Total"]
        )
        configure_table(table, stretch_last=False)
        table.verticalHeader().setDefaultSectionSize(row_h)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        hdr = table.horizontalHeader()
        for col in range(8):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)

        supplier_texts = []
        for r_idx, row in enumerate(visible_rows):
            date_item = QtWidgets.QTableWidgetItem(_date_only_text(row["date"]))
            supplier_txt = str(row["supplier"])
            supplier_texts.append(supplier_txt)
            supplier_item = QtWidgets.QTableWidgetItem(supplier_txt)
            qty_item = QtWidgets.QTableWidgetItem(str(row["qty"]))
            retail_item = QtWidgets.QTableWidgetItem(f"{row['retail']:.2f}")
            trade_item = QtWidgets.QTableWidgetItem(f"{row['trade']:.2f}")
            disc_val = "" if row["disc"] is None else f"{row['disc']:.2f}"
            extra_val = "" if row["extra"] is None else f"{row['extra']:.2f}"
            disc_item = QtWidgets.QTableWidgetItem(disc_val)
            extra_item = QtWidgets.QTableWidgetItem(extra_val)
            line_total_item = QtWidgets.QTableWidgetItem(f"{row['final'] * row['qty']:.2f}")

            date_item.setTextAlignment(QtCore.Qt.AlignCenter)
            qty_item.setTextAlignment(QtCore.Qt.AlignCenter)
            retail_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            trade_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            disc_item.setTextAlignment(QtCore.Qt.AlignCenter)
            extra_item.setTextAlignment(QtCore.Qt.AlignCenter)
            line_total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

            table.setItem(r_idx, 0, date_item)
            table.setItem(r_idx, 1, supplier_item)
            table.setItem(r_idx, 2, qty_item)
            table.setItem(r_idx, 3, retail_item)
            table.setItem(r_idx, 4, trade_item)
            table.setItem(r_idx, 5, disc_item)
            table.setItem(r_idx, 6, extra_item)
            table.setItem(r_idx, 7, line_total_item)

        fm = table.fontMetrics()
        supplier_pref = fm.horizontalAdvance("Supplier") + 28
        for txt in supplier_texts:
            supplier_pref = max(supplier_pref, fm.horizontalAdvance(txt) + 30)
        supplier_pref = min(420, supplier_pref)
        pref_widths = {
            0: 106,
            1: supplier_pref,
            2: 58,
            3: 96,
            4: 96,
            5: 70,
            6: 70,
            7: 112,
        }
        min_widths = {
            0: 92,
            1: 150,
            2: 50,
            3: 82,
            4: 82,
            5: 60,
            6: 60,
            7: 94,
        }
        widths = dict(pref_widths)
        table_frame = table.frameWidth() * 2 + 2
        available_table_w = max(520, max_dlg_w - 24 - table_frame)
        overflow = max(0, sum(widths.values()) - available_table_w)
        if overflow > 0:
            supplier_cut = min(overflow, widths[1] - min_widths[1])
            widths[1] -= supplier_cut
            overflow -= supplier_cut
            for col in (0, 3, 4, 7, 5, 6, 2):
                if overflow <= 0:
                    break
                cut = min(overflow, widths[col] - min_widths[col])
                widths[col] -= cut
                overflow -= cut
        for col, width in widths.items():
            table.setColumnWidth(col, int(width))
        table_w = sum(widths.values()) + table_frame
        table_h = table.frameWidth() * 2 + table.horizontalHeader().height() + (table.rowCount() * row_h) + 2
        table.setFixedSize(table_w, table_h)
        v.addWidget(table)
        if hidden_count > 0:
            info_lbl = QtWidgets.QLabel(
                f"Showing latest {len(visible_rows)} of {len(rows)} purchases to fit the screen without scrolling."
            )
            info_lbl.setObjectName("mutedLabel")
            v.addWidget(info_lbl)
        close_btn = QtWidgets.QPushButton("Close")
        set_secondary(close_btn)
        close_btn.clicked.connect(dlg.accept)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)
        polish_controls(dlg)
        dlg.adjustSize()
        dlg.setFixedSize(min(max_dlg_w, dlg.sizeHint().width()), min(max_dlg_h, dlg.sizeHint().height()))
        dlg.exec_()

    def _show_sales_history(self):
        sel = self._selected_product_for_history()
        if not sel:
            QtWidgets.QMessageBox.information(
                self,
                "Select product",
                "Select a product in the cart or search results to view its sales history.",
            )
            return
        pid, name = sel

        try:
            selected_customer_id = int(self.customer.currentData() or 0)
        except Exception:
            selected_customer_id = 0
        selected_customer_name = str(self.customer.currentText() or "").strip() or "Walk-in"

        customer_name_by_id = {0: "Walk-in"}
        for idx in range(self.customer.count()):
            try:
                cid = int(self.customer.itemData(idx) or 0)
            except Exception:
                cid = 0
            cname = str(self.customer.itemText(idx) or "").strip()
            if cname:
                customer_name_by_id[cid] = cname

        try:
            docs = self._with_loader("Loading sales history...", self.api.transactions_list) or []
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return

        def _to_float(value, fallback=0.0):
            try:
                return float(value if value is not None else fallback)
            except Exception:
                return float(fallback)

        rows = []
        for txn in docs:
            try:
                cust_id = int(txn.get("customer_id", 0) or 0)
            except Exception:
                cust_id = 0
            if cust_id != selected_customer_id:
                continue
            date = txn.get("date", "")
            for it in txn.get("items") or []:
                try:
                    item_pid = int(it.get("id", 0) or 0)
                except Exception:
                    item_pid = 0
                if item_pid != pid:
                    continue
                try:
                    qty = int(it.get("quantity", 0) or 0)
                except Exception:
                    qty = 0
                if qty <= 0:
                    continue
                retail = _to_float(it.get("retail_price"), 0.0)
                disc = it.get("discount_pct", None)
                extra = it.get("extra_discount_pct", None)
                trade = _to_float(it.get("trade_price"), retail)
                unit = _to_float(it.get("unit_price"), trade)
                try:
                    disc = float(disc) if disc is not None else None
                except Exception:
                    disc = None
                try:
                    extra = float(extra) if extra is not None else None
                except Exception:
                    extra = None
                rows.append(
                    {
                        "date": date,
                        "customer": customer_name_by_id.get(cust_id, selected_customer_name or "Walk-in"),
                        "qty": qty,
                        "retail": retail,
                        "trade": trade,
                        "disc": disc,
                        "extra": extra,
                        "line_total": unit * qty,
                    }
                )

        if not rows:
            QtWidgets.QMessageBox.information(
                self,
                "No history",
                "No recent sales found for this product for the selected customer.",
            )
            return

        rows.sort(key=lambda r: r.get("date", ""), reverse=True)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            max_dlg_w = int(geo.width() * 0.92)
            max_dlg_h = int(geo.height() * 0.90)
        else:
            max_dlg_w = 1180
            max_dlg_h = 760

        row_h = 32
        header_h = 34
        chrome_h = 180  # title + optional note + buttons + margins
        max_rows_fit = max(1, int((max_dlg_h - chrome_h - header_h) / max(1, row_h)))
        visible_rows = rows[:max_rows_fit]
        hidden_count = max(0, len(rows) - len(visible_rows))

        def _date_only_text(raw_value):
            dt = str(raw_value or "").strip()
            if not dt:
                return ""
            try:
                parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                return parsed.strftime("%d-%m-%Y")
            except Exception:
                normalized = dt.replace("T", " ")
                parts = normalized.split()
                date_txt = parts[0] if parts else normalized
                try:
                    return datetime.strptime(date_txt, "%Y-%m-%d").strftime("%d-%m-%Y")
                except Exception:
                    return date_txt

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Sales for {name} ({selected_customer_name})")
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        v.addWidget(QtWidgets.QLabel(f"Recent sales for {name} - Customer: {selected_customer_name}"))
        table = QtWidgets.QTableWidget(len(visible_rows), 8)
        table.setHorizontalHeaderLabels(
            ["Date", "Customer", "Qty", "Retail", "Trade", "%Disc", "Addl %", "Line Total"]
        )
        configure_table(table, stretch_last=False)
        table.verticalHeader().setDefaultSectionSize(row_h)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        hdr = table.horizontalHeader()
        for col in range(8):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)

        customer_texts = []
        for r_idx, row in enumerate(visible_rows):
            date_item = QtWidgets.QTableWidgetItem(_date_only_text(row["date"]))
            customer_txt = str(row["customer"])
            customer_texts.append(customer_txt)
            customer_item = QtWidgets.QTableWidgetItem(customer_txt)
            qty_item = QtWidgets.QTableWidgetItem(str(row["qty"]))
            retail_item = QtWidgets.QTableWidgetItem(f"{row['retail']:.2f}")
            trade_item = QtWidgets.QTableWidgetItem(f"{row['trade']:.2f}")
            disc_val = "" if row["disc"] is None else f"{row['disc']:.2f}"
            extra_val = "" if row["extra"] is None else f"{row['extra']:.2f}"
            disc_item = QtWidgets.QTableWidgetItem(disc_val)
            extra_item = QtWidgets.QTableWidgetItem(extra_val)
            line_total_item = QtWidgets.QTableWidgetItem(f"{row['line_total']:.2f}")

            date_item.setTextAlignment(QtCore.Qt.AlignCenter)
            qty_item.setTextAlignment(QtCore.Qt.AlignCenter)
            retail_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            trade_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            disc_item.setTextAlignment(QtCore.Qt.AlignCenter)
            extra_item.setTextAlignment(QtCore.Qt.AlignCenter)
            line_total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

            table.setItem(r_idx, 0, date_item)
            table.setItem(r_idx, 1, customer_item)
            table.setItem(r_idx, 2, qty_item)
            table.setItem(r_idx, 3, retail_item)
            table.setItem(r_idx, 4, trade_item)
            table.setItem(r_idx, 5, disc_item)
            table.setItem(r_idx, 6, extra_item)
            table.setItem(r_idx, 7, line_total_item)

        fm = table.fontMetrics()
        customer_pref = fm.horizontalAdvance("Customer") + 28
        for txt in customer_texts:
            customer_pref = max(customer_pref, fm.horizontalAdvance(txt) + 30)
        customer_pref = min(420, customer_pref)
        pref_widths = {
            0: 106,
            1: customer_pref,
            2: 58,
            3: 96,
            4: 96,
            5: 70,
            6: 70,
            7: 112,
        }
        min_widths = {
            0: 92,
            1: 150,
            2: 50,
            3: 82,
            4: 82,
            5: 60,
            6: 60,
            7: 94,
        }
        widths = dict(pref_widths)
        table_frame = table.frameWidth() * 2 + 2
        available_table_w = max(520, max_dlg_w - 24 - table_frame)
        overflow = max(0, sum(widths.values()) - available_table_w)
        if overflow > 0:
            customer_cut = min(overflow, widths[1] - min_widths[1])
            widths[1] -= customer_cut
            overflow -= customer_cut
            for col in (0, 3, 4, 7, 5, 6, 2):
                if overflow <= 0:
                    break
                cut = min(overflow, widths[col] - min_widths[col])
                widths[col] -= cut
                overflow -= cut
        for col, width in widths.items():
            table.setColumnWidth(col, int(width))
        table_w = sum(widths.values()) + table_frame
        table_h = table.frameWidth() * 2 + table.horizontalHeader().height() + (table.rowCount() * row_h) + 2
        table.setFixedSize(table_w, table_h)
        v.addWidget(table)
        if hidden_count > 0:
            info_lbl = QtWidgets.QLabel(
                f"Showing latest {len(visible_rows)} of {len(rows)} sales to fit the screen without scrolling."
            )
            info_lbl.setObjectName("mutedLabel")
            v.addWidget(info_lbl)
        close_btn = QtWidgets.QPushButton("Close")
        set_secondary(close_btn)
        close_btn.clicked.connect(dlg.accept)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)
        polish_controls(dlg)
        dlg.adjustSize()
        dlg.setFixedSize(min(max_dlg_w, dlg.sizeHint().width()), min(max_dlg_h, dlg.sizeHint().height()))
        dlg.exec_()

    def _reopen_invoice_by_number(self):
        raw = (self.invoice_no.text() or "").strip()
        if not raw or not raw.isdigit():
            QtWidgets.QMessageBox.information(self, "Invoice", "Enter a valid invoice number.")
            return
        invoice_id = int(raw)
        if invoice_id <= 0:
            QtWidgets.QMessageBox.information(self, "Invoice", "Enter a valid invoice number.")
            return
        if self.table.rowCount() > 0:
            if QtWidgets.QMessageBox.question(
                self,
                "Replace Cart",
                "Current cart items will be replaced. Continue?",
            ) != QtWidgets.QMessageBox.Yes:
                return
        try:
            txn = self._with_loader("Loading invoice...", lambda: self.api.transaction_get(invoice_id))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        if not isinstance(txn, dict) or int(txn.get("id", 0) or 0) != invoice_id:
            detail = ""
            if isinstance(txn, dict):
                detail = str(txn.get("detail", "") or "").strip()
            if detail:
                QtWidgets.QMessageBox.information(self, "Invoice", detail)
            else:
                QtWidgets.QMessageBox.information(self, "Invoice", "Invoice not found.")
            return
        self._load_transaction_into_cart(txn)
        self.invoice_no.clear()

    def _invoice_id_for_payments(self):
        if self._edit_transaction_id is not None:
            return int(self._edit_transaction_id)
        return None

    def _show_invoice_payments(self):
        inv = self._invoice_id_for_payments()
        if inv is None:
            QtWidgets.QMessageBox.information(self, "Payments", "Reopen an invoice first.")
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
            4: 84,   # User ID
        }

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Payments for Invoice #{inv}")
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        table = QtWidgets.QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Date", "Time", "Amount", "Paid Total", "User ID", "Payment ID"])
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
        info = QtWidgets.QLabel("You can edit a payment amount and it will recalculate paid totals.")
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
                rows = self._with_loader("Loading payment history...", lambda: self.api.transaction_payments(inv)) or []
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return False
            if isinstance(rows, dict):
                detail = str(rows.get("detail", "") or "").strip()
                QtWidgets.QMessageBox.information(self, "Payments", detail or "Could not load payment history.")
                return False
            rows = list(rows or [])
            rows.sort(key=lambda row: str(row.get("date", "") or ""), reverse=True)
            state["total_rows"] = len(rows)
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
                pid = int(row.get("id", 0) or 0)
                date_item = QtWidgets.QTableWidgetItem(date_txt)
                time_item = QtWidgets.QTableWidgetItem(time_txt)
                amount_item = QtWidgets.QTableWidgetItem(amt)
                paid_total_item = QtWidgets.QTableWidgetItem(f"{paid_total:.2f}")
                user_item = QtWidgets.QTableWidgetItem(str(uid))
                date_item.setTextAlignment(QtCore.Qt.AlignCenter)
                time_item.setTextAlignment(QtCore.Qt.AlignCenter)
                amount_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                paid_total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                user_item.setTextAlignment(QtCore.Qt.AlignCenter)
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
                resp = self._with_loader(
                    "Saving payment...",
                    lambda: self.api.transaction_payment_update(inv, payment_id, float(new_amount)),
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                QtWidgets.QMessageBox.information(self, "Payments", str(resp.get("detail")))
                return
            _load_rows()
            self._sync_payment_edit_state(inv)

        if not _load_rows():
            return
        if state["total_rows"] <= 0:
            QtWidgets.QMessageBox.information(self, "Payments", f"No payment entries for invoice #{inv}.")
            return
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        edit_btn = QtWidgets.QPushButton("Edit Selected")
        edit_btn.clicked.connect(_edit_selected)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(_load_rows)
        set_secondary(edit_btn, refresh_btn, close_btn)
        row_btn = QtWidgets.QHBoxLayout()
        row_btn.addWidget(edit_btn)
        row_btn.addWidget(refresh_btn)
        row_btn.addStretch(1)
        row_btn.addWidget(close_btn)
        v.addLayout(row_btn)
        polish_controls(dlg)
        _fit_dialog()
        dlg.exec_()

    def _sync_payment_edit_state(self, invoice_id: int):
        try:
            txn = self.api.transaction_get(int(invoice_id))
        except Exception:
            return
        if not isinstance(txn, dict) or int(txn.get("id", 0) or 0) != int(invoice_id):
            return
        if self._edit_transaction_id is not None and int(self._edit_transaction_id) == int(invoice_id):
            try:
                self._edit_existing_paid = max(0.0, float(txn.get("paid", 0.0) or 0.0))
            except Exception:
                self._edit_existing_paid = 0.0
            self.paid_spin.setValue(0.0)
            self._recalc_totals()
            self._load_products_cache()

    def _load_transaction_into_cart(self, txn: dict):
        tx_id = int(txn.get("id", 0) or 0)
        raw_items = txn.get("items") or []
        items = []
        original_qty_map: dict[int, int] = {}
        for it in raw_items:
            try:
                pid = int(it.get("id", 0) or 0)
                qty = max(0, int(it.get("quantity", 0) or 0))
            except Exception:
                continue
            if pid <= 0 or qty <= 0:
                continue
            items.append(
                {
                    "id": pid,
                    "quantity": qty,
                    "name": it.get("name"),
                    "retail_price": it.get("retail_price"),
                    "discount_pct": it.get("discount_pct"),
                    "extra_discount_pct": it.get("extra_discount_pct"),
                    "trade_price": it.get("trade_price"),
                    "unit_price": it.get("unit_price"),
                }
            )
            original_qty_map[pid] = int(original_qty_map.get(pid, 0) or 0) + qty
        if tx_id <= 0 or not items:
            QtWidgets.QMessageBox.information(self, "Invoice", "Invoice has no editable items.")
            return
        self._load_products_cache()
        try:
            existing_paid = float(txn.get("paid", 0.0) or 0.0)
        except Exception:
            existing_paid = 0.0
        self._set_invoice_edit_mode(tx_id, original_qty_map, existing_paid=existing_paid)
        self._clear_cart()
        try:
            cust_id = int(txn.get("customer_id", 0) or 0)
        except Exception:
            cust_id = 0
        idx = self.customer.findData(cust_id)
        self.customer.setCurrentIndex(idx if idx >= 0 else 0)
        try:
            self.discount.setValue(float(txn.get("discount", 0.0) or 0.0))
        except Exception:
            self.discount.setValue(0.0)

        skipped = []
        for it in items:
            pid = int(it["id"])
            qty = int(it["quantity"])
            prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == pid), None)
            if not prod:
                row_seed = {
                    "id": pid,
                    "name": str(it.get("name") or f"Product #{pid}"),
                    "company_id": 0,
                    "company_name": "",
                    "price": float(it.get("retail_price", 0.0) or 0.0),
                    "quantity": int(original_qty_map.get(pid, 0) or 0),
                    "discount_pct": float(it.get("discount_pct", 0.0) or 0.0),
                    "trade_price": float(it.get("trade_price", 0.0) or 0.0),
                    "extra_discount_pct": float(it.get("extra_discount_pct", 0.0) or 0.0),
                }
            else:
                row_seed = dict(prod)
                if it.get("name") is not None:
                    row_seed["name"] = str(it.get("name") or row_seed.get("name", ""))
                if it.get("retail_price") is not None:
                    row_seed["price"] = float(it.get("retail_price", 0.0) or 0.0)
                if it.get("discount_pct") is not None:
                    row_seed["discount_pct"] = float(it.get("discount_pct", 0.0) or 0.0)
                if it.get("trade_price") is not None:
                    row_seed["trade_price"] = float(it.get("trade_price", 0.0) or 0.0)
                if it.get("extra_discount_pct") is not None:
                    row_seed["extra_discount_pct"] = float(it.get("extra_discount_pct", 0.0) or 0.0)

            row = self._add_product_to_cart(row_seed)
            if row is None:
                skipped.append(str(pid))
                continue
            qty_spin = self.table.cellWidget(row, 5)
            if isinstance(qty_spin, QtWidgets.QSpinBox):
                qty_spin.setValue(qty)
            # Ensure row mirrors saved invoice fields even if product master changed.
            try:
                if it.get("retail_price") is not None:
                    self.table.cellWidget(row, 1).setValue(float(it.get("retail_price", 0.0) or 0.0))
                if it.get("discount_pct") is not None:
                    self.table.cellWidget(row, 2).setValue(float(it.get("discount_pct", 0.0) or 0.0))
                if it.get("extra_discount_pct") is not None:
                    self.table.cellWidget(row, 4).setValue(float(it.get("extra_discount_pct", 0.0) or 0.0))
                if it.get("trade_price") is not None:
                    self.table.item(row, 3).setText(f"{float(it.get('trade_price', 0.0) or 0.0):.2f}")
            except Exception:
                pass
            self._recalc_row(row)

        self._recalc_totals()
        if self.table.rowCount() <= 0:
            self._exit_invoice_edit_mode()
            QtWidgets.QMessageBox.information(self, "Invoice", "Could not load invoice into cart.")
            return
        if skipped:
            QtWidgets.QMessageBox.warning(
                self,
                "Invoice",
                f"Some invoice items could not be loaded ({', '.join(skipped)}).",
            )
        self._focus_cart_cell(0, 2)

    # ---------- Cart ops ----------
    def _make_money_spin(self, value):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setMaximum(10**9)
        spin.setDecimals(2)
        spin.setValue(float(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        spin.setObjectName("cartEditor")
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setMinimumHeight(34)
        return spin

    def _make_pct_spin(self, value):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setDecimals(2)
        spin.setValue(float(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        spin.setObjectName("cartEditor")
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setMinimumHeight(34)
        return spin

    def _make_qty_spin(self, value):
        spin = QtWidgets.QSpinBox()
        spin.setRange(1, 10**9)
        spin.setValue(int(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        spin.setObjectName("cartEditor")
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setMinimumHeight(34)
        return spin

    def _safe_float(self, value, default=None):
        try:
            return float(value)
        except Exception:
            return default

    def _find_product_in_cache(self, product_id: int):
        pid = int(product_id or 0)
        if pid <= 0:
            return None
        for prod in self.products_cache or []:
            try:
                if int(prod.get("id", 0) or 0) == pid:
                    return prod
            except Exception:
                continue
        return None

    def _estimate_cost_unit(self, product: dict):
        pid = int(product.get("id", 0) or 0)
        src = self._find_product_in_cache(pid) or product or {}
        for key in ("cost_price", "purchase_price", "trade_price"):
            val = self._safe_float(src.get(key), None)
            if val is not None and val > 0:
                return float(val)
        retail = self._safe_float(src.get("price"), None)
        discount = self._safe_float(src.get("discount_pct"), None)
        if discount is None:
            discount = self._safe_float(src.get("purchase_discount"), None)
        if retail is not None and retail > 0 and discount is not None:
            return max(0.0, float(retail) * (1.0 - (max(0.0, float(discount)) / 100.0)))
        return None

    def _ensure_margin_tag_item(self, row: int):
        item = self.table.item(row, 7)
        if item is None:
            item = QtWidgets.QTableWidgetItem("")
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)
            self.table.setItem(row, 7, item)
        return item

    def _update_row_margin_tag(self, row: int):
        if row < 0 or row >= self.table.rowCount():
            return
        product_item = self.table.item(row, 0)
        trade_item = self.table.item(row, 3)
        if product_item is None or trade_item is None:
            return
        margin_item = self._ensure_margin_tag_item(row)
        meta = product_item.data(QtCore.Qt.UserRole) or {}
        cost_unit = self._safe_float(meta.get("cost_unit_estimate"), None)
        if cost_unit is None or cost_unit <= 1e-9:
            margin_item.setText("COST ?")
            margin_item.setForeground(QtGui.QBrush(QtGui.QColor("#89A1C2")))
            return
        try:
            trade = float(trade_item.text() or 0.0)
            extra = float(self.table.cellWidget(row, 4).value() or 0.0)
            qty = int(self.table.cellWidget(row, 5).value() or 0)
            global_discount = float(self.discount.value() or 0.0)
        except Exception:
            return
        unit_sale = max(0.0, trade * (1.0 - (extra / 100.0)) * (1.0 - (global_discount / 100.0)))
        line_profit = float(qty) * (unit_sale - float(cost_unit))
        if line_profit < -0.005:
            margin_item.setText(f"LOSS {line_profit:.2f}")
            margin_item.setForeground(QtGui.QBrush(QtGui.QColor("#F04438")))
            return
        if abs(line_profit) <= 0.005:
            margin_item.setText("ZERO PROFIT")
            margin_item.setForeground(QtGui.QBrush(QtGui.QColor("#FDB022")))
            return
        margin_item.setText("")
        margin_item.setForeground(QtGui.QBrush(QtGui.QColor("#89A1C2")))

    def _add_product_to_cart(self, product: dict):
        row = self.table.rowCount()
        pid_for_stock = int(product.get("id", 0) or 0)
        if pid_for_stock:
            try:
                current_stock = int(product.get("quantity", 0) or 0)
            except Exception:
                current_stock = 0
            existing_row = self._find_row_for_product(pid_for_stock)
            if existing_row is not None:
                if current_stock <= 0:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Out of stock",
                        "Current stock is zero. Product is already in cart and stock can go negative.",
                    )
                QtWidgets.QMessageBox.information(self, "Already added", "This product is already in the cart.")
                self._focus_cart_cell(existing_row, 5)
                return existing_row
            available = self._available_stock(pid_for_stock)
            if available <= 0 or current_stock <= 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Out of stock",
                    "Current stock is zero. Product will be added and stock can go negative.",
                )
        self.table.insertRow(row)

        # Product column
        name = str(product.get("name", ""))
        company = str(product.get("company_name", ""))
        label = f"{name} ({company})" if company else name
        prod_item = QtWidgets.QTableWidgetItem(label)
        prod_item.setFlags(prod_item.flags() & ~QtCore.Qt.ItemIsEditable)
        prod_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        prod_item.setForeground(QtGui.QBrush(QtGui.QColor("#f5f9ff")))
        prod_item.setData(
            QtCore.Qt.UserRole,
            {
                "id": int(product.get("id", 0) or 0),
                "company_id": int(product.get("company_id", 0) or 0),
                "name": str(product.get("name", "") or ""),
                "cost_unit_estimate": self._estimate_cost_unit(product),
            },
        )
        self.table.setItem(row, 0, prod_item)

        # Retail (disabled money spin)
        retail = float(product.get("price", 0.0) or 0.0)
        retail_spin = self._make_money_spin(retail)
        retail_spin.setEnabled(False)
        self.table.setCellWidget(row, 1, retail_spin)

        # % Discount, Trade, Addl %, Qty
        raw_pct = product.get("discount_pct")
        if raw_pct is None:
            raw_pct = product.get("purchase_discount")
        try:
            pct_default = float(raw_pct) if raw_pct is not None else None
        except Exception:
            pct_default = None
        try:
            raw_trade = product.get("trade_price", None)
            trade_default = float(raw_trade) if raw_trade is not None else None
        except Exception:
            trade_default = None
        if pct_default is None and trade_default is not None and retail > 0:
            try:
                pct_default = max(0.0, (1.0 - (trade_default / retail)) * 100.0)
            except Exception:
                pct_default = None
        if trade_default is None and pct_default is not None:
            try:
                trade_default = retail * (1.0 - (pct_default / 100.0))
            except Exception:
                trade_default = None
        try:
            extra_default = float(product.get("extra_discount_pct", 0.0) or 0.0)
        except Exception:
            extra_default = 0.0
        pct_spin = self._make_pct_spin(pct_default or 0.0)
        trade_item = QtWidgets.QTableWidgetItem(f"{float(trade_default or retail):.2f}")
        trade_item.setFlags(trade_item.flags() & ~QtCore.Qt.ItemIsEditable)
        trade_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
        trade_item.setForeground(QtGui.QBrush(QtGui.QColor("#f2f7ff")))
        extra_spin = self._make_pct_spin(extra_default)
        qty_spin = self._make_qty_spin(1)
        self.table.setCellWidget(row, 2, pct_spin)
        self.table.setItem(row, 3, trade_item)
        self.table.setCellWidget(row, 4, extra_spin)
        self.table.setCellWidget(row, 5, qty_spin)

        # Line total
        line_total = QtWidgets.QTableWidgetItem("0.00")
        line_total.setFlags(line_total.flags() & ~QtCore.Qt.ItemIsEditable)
        line_total.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
        line_total.setForeground(QtGui.QBrush(QtGui.QColor("#f2f7ff")))
        self.table.setItem(row, 6, line_total)

        margin_tag = QtWidgets.QTableWidgetItem("")
        margin_tag.setFlags(margin_tag.flags() & ~QtCore.Qt.ItemIsEditable)
        margin_tag.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)
        margin_tag.setForeground(QtGui.QBrush(QtGui.QColor("#89A1C2")))
        self.table.setItem(row, 7, margin_tag)

        # Connect recalc triggers
        for col in (1, 2, 4, 5):
            w = self.table.cellWidget(row, col)
            if w:
                w.valueChanged.connect(lambda _=None, rr=row: self._on_row_value_changed(rr))
        # Capture arrow keys directly from editors for fast keyboard navigation.
        for col in (2, 4, 5):
            w = self.table.cellWidget(row, col)
            if w:
                w.installEventFilter(self)
                try:
                    le = w.lineEdit() if hasattr(w, "lineEdit") else None
                except Exception:
                    le = None
                if le is not None:
                    le.installEventFilter(self)
        # Allow keyboard focus without mouse
        self._focus_cart_cell(row, 2)
        self._recalc_row(row)
        self._recalc_totals()
        return row

    def _remove_row(self, row: int):
        if 0 <= row < self.table.rowCount():
            self.table.removeRow(row)
            if self.table.rowCount() > 0:
                next_row = min(row, self.table.rowCount() - 1)
                self._focus_cart_cell(next_row, 2)
            self._recalc_totals()

    def _remove_selected_row(self):
        r = self.table.currentRow()
        if r < 0:
            focus_w = self.focusWidget()
            focus_row, _ = self._cart_widget_position(focus_w)
            r = focus_row if focus_row is not None else -1
        if r >= 0:
            self._remove_row(r)

    def _clear_cart(self):
        self.table.setRowCount(0)
        self._recalc_totals()
        self.discount.setValue(0.0)
        self.paid_spin.setValue(0.0)

    def _available_stock(self, product_id: int, exclude_row: int | None = None) -> int:
        """Return remaining stock after accounting for items already in cart."""
        try:
            prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == product_id), None)
            stock = int(prod.get("quantity", 0)) if prod else 0
        except Exception:
            stock = 0
        # When editing an existing invoice, include previously deducted qty for that invoice.
        try:
            stock += int(self._edit_original_qty_by_product.get(int(product_id), 0) or 0)
        except Exception:
            pass
        # Subtract quantities already in cart for this product
        used = 0
        for r in range(self.table.rowCount()):
            if exclude_row is not None and r == exclude_row:
                continue
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                if int(meta.get("id", 0) or 0) == product_id:
                    used += int(self.table.cellWidget(r, 5).value())
            except Exception:
                pass
        return max(0, stock - used)

    def _recalc_row(self, r: int):
        try:
            retail = float(self.table.cellWidget(r, 1).value())
            pct = float(self.table.cellWidget(r, 2).value())
            extra = float(self.table.cellWidget(r, 4).value())
            qty = int(self.table.cellWidget(r, 5).value())
            trade = retail * (1.0 - (pct / 100.0))
            final = trade * (1.0 - (extra / 100.0))
            self.table.item(r, 3).setText(f"{trade:.2f}")
            self.table.item(r, 6).setText(f"{final * qty:.2f}")
            self._update_row_margin_tag(r)
            # Refresh totals when any row value changes
            self._recalc_totals()
        except Exception:
            pass

    def _on_row_value_changed(self, r: int):
        # Warn once when user moves this line into negative stock range.
        try:
            meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
            pid = int(meta.get("id", 0) or 0)
            qty_spin = self.table.cellWidget(r, 5)
            if pid and isinstance(qty_spin, QtWidgets.QSpinBox):
                max_qty = self._available_stock(pid, exclude_row=r)
                over = int(qty_spin.value()) > int(max_qty)
                warned = bool(qty_spin.property("overstock_warned") or False)
                if over and not warned:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Stock warning",
                        "Entered quantity is higher than available stock. Stock will go negative.",
                    )
                qty_spin.setProperty("overstock_warned", over)
        except Exception:
            pass
        self._recalc_row(r)

    def _focus_next_cart_field(self):
        """Move focus to the next editable cart field (discount -> addl -> qty -> next row)."""
        editable_cols = [2, 4, 5]  # discount, addl %, qty
        row = self.table.currentRow()
        if row < 0 and self.table.rowCount() > 0:
            row = 0
            self.table.setCurrentCell(row, editable_cols[0])
        current_col = self.table.currentColumn()
        focus_w = self.focusWidget()
        # Try to infer current column from focused widget
        if focus_w:
            for c in editable_cols:
                if self.table.cellWidget(row, c) is focus_w:
                    current_col = c
                    break
        try:
            idx = editable_cols.index(current_col)
        except ValueError:
            idx = -1
        # If we're on qty (end of row)
        if current_col == 5 or idx == len(editable_cols) - 1:
            if row + 1 < self.table.rowCount():
                # Move to next row's discount
                self._focus_cart_cell(row + 1, editable_cols[0])
            else:
                # Last row: go back to search to add next product
                self._focus_search()
            return
        if idx + 1 < len(editable_cols):
            next_col = editable_cols[idx + 1]
            next_row = row
        else:
            next_col = editable_cols[0]
            next_row = row + 1
        if next_row >= self.table.rowCount():
            next_row = row  # stay on last row
        self._focus_cart_cell(next_row, next_col)

    def _focus_prev_cart_field(self):
        """Move focus to previous editable cart field (qty -> addl -> discount -> prev row)."""
        editable_cols = [2, 4, 5]
        row = self.table.currentRow()
        if row < 0:
            if self.table.rowCount() <= 0:
                return
            row = 0
            self.table.setCurrentCell(row, editable_cols[0])
        current_col = self.table.currentColumn()
        focus_w = self.focusWidget()
        if focus_w:
            for c in editable_cols:
                if self.table.cellWidget(row, c) is focus_w:
                    current_col = c
                    break
                w = self.table.cellWidget(row, c)
                try:
                    le = w.lineEdit() if (w is not None and hasattr(w, "lineEdit")) else None
                except Exception:
                    le = None
                if le is focus_w:
                    current_col = c
                    break
        try:
            idx = editable_cols.index(current_col)
        except ValueError:
            idx = 0
        if current_col == editable_cols[0] or idx <= 0:
            if row - 1 >= 0:
                self._focus_cart_cell(row - 1, editable_cols[-1])
            else:
                self._focus_search()
            return
        prev_col = editable_cols[idx - 1]
        self._focus_cart_cell(row, prev_col)

    def _cart_widget_position(self, obj):
        """Find table row/col for a cart editor widget or its inner line edit."""
        for r in range(self.table.rowCount()):
            for c in (2, 4, 5):
                w = self.table.cellWidget(r, c)
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

    def _focus_cart_cell(self, row: int, col: int):
        self.table.setCurrentCell(row, col)
        w = self.table.cellWidget(row, col)
        if w:
            w.setFocus()
            if hasattr(w, "lineEdit") and w.lineEdit():
                try:
                    w.lineEdit().selectAll()
                except Exception:
                    pass

    def _move_cart_row(self, delta: int, preferred_col: int | None = None):
        """Move cart focus vertically without changing current field values."""
        if self.table.rowCount() <= 0:
            return
        row = self.table.currentRow()
        if row < 0:
            row = 0
        col = self.table.currentColumn()
        if preferred_col is not None:
            col = preferred_col
        if col not in (2, 4, 5):
            col = 2
        new_row = max(0, min(self.table.rowCount() - 1, row + delta))
        self._focus_cart_cell(new_row, col)

    def _focus_cart_from_search(self):
        """Jump from search box to an editable field in the active cart row."""
        if self.table.rowCount() <= 0:
            return
        row = self.table.currentRow()
        if row < 0 or row >= self.table.rowCount():
            row = self.table.rowCount() - 1
        self._focus_cart_cell(row, 2)

    def _find_row_for_product(self, pid: int):
        for r in range(self.table.rowCount()):
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                if int(meta.get("id", 0) or 0) == pid:
                    return r
            except Exception:
                pass
        return None

    # ---------- Hold/Resume ----------
    def _load_held_sales(self):
        try:
            raw = self.api.held_sales_list() or []
        except Exception:
            self.held_sales = []
            return False
        if isinstance(raw, dict):
            self.held_sales = []
            return False

        def _as_int(value, default=0):
            try:
                return int(value)
            except Exception:
                return int(default)

        def _as_float(value, default=0.0):
            try:
                return float(value)
            except Exception:
                return float(default)

        cleaned: list[dict] = []
        for snap in raw:
            if not isinstance(snap, dict):
                continue
            items_raw = snap.get("items", [])
            if not isinstance(items_raw, list):
                continue
            items = []
            for it in items_raw:
                if not isinstance(it, dict):
                    continue
                pid = _as_int(it.get("product_id", 0), 0)
                qty = max(0, _as_int(it.get("qty", 0), 0))
                if pid <= 0 or qty <= 0:
                    continue
                items.append(
                    {
                        "product_id": pid,
                        "company_id": _as_int(it.get("company_id", 0), 0),
                        "retail": _as_float(it.get("retail", 0.0), 0.0),
                        "pct": _as_float(it.get("pct", 0.0), 0.0),
                        "trade": _as_float(it.get("trade", 0.0), 0.0),
                        "extra": _as_float(it.get("extra", 0.0), 0.0),
                        "qty": qty,
                        "label": str(it.get("label", "") or ""),
                    }
                )
            if not items:
                continue
            cleaned.append(
                {
                    "id": _as_int(snap.get("id", 0), 0),
                    "name": str(snap.get("name", "") or "").strip() or f"Hold {_as_int(len(cleaned) + 1, 1)}",
                    "created": str(snap.get("created", "") or "").strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "customer_id": _as_int(snap.get("customer_id", 0), 0),
                    "discount": _as_float(snap.get("discount", 0.0), 0.0),
                    "paid": _as_float(snap.get("paid", 0.0), 0.0),
                    "items": items,
                }
            )
        self.held_sales = cleaned
        return True

    def _snapshot_cart(self) -> dict:
        items = []
        for r in range(self.table.rowCount()):
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                pid = int(meta.get("id", 0) or 0)
                cid = int(meta.get("company_id", 0) or 0)
                retail = float(self.table.cellWidget(r, 1).value())
                pct = float(self.table.cellWidget(r, 2).value())
                trade = float(self.table.item(r, 3).text() or 0.0)
                extra = float(self.table.cellWidget(r, 4).value())
                qty = int(self.table.cellWidget(r, 5).value())
                items.append(
                    {
                        "product_id": pid,
                        "company_id": cid,
                        "retail": retail,
                        "pct": pct,
                        "trade": trade,
                        "extra": extra,
                        "qty": qty,
                        "label": self.table.item(r, 0).text(),
                    }
                )
            except Exception:
                pass
        try:
            cust_id = int(self.customer.currentData() or 0)
        except Exception:
            cust_id = 0
        return {
            "items": items,
            "discount": float(self.discount.value() or 0.0),
            "paid": float(self.paid_spin.value() or 0.0),
            "customer_id": cust_id,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _load_cart_from_snapshot(self, snap: dict):
        self._clear_cart()
        # Restore customer and discount
        cust_id = int(snap.get("customer_id", 0) or 0)
        if cust_id:
            idx = self.customer.findData(cust_id)
            if idx >= 0:
                self.customer.setCurrentIndex(idx)
        self.discount.setValue(float(snap.get("discount", 0.0) or 0.0))
        self.paid_spin.setValue(float(snap.get("paid", 0.0) or 0.0))
        # Restore items
        for it in snap.get("items", []):
            pid = int(it.get("product_id", 0) or 0)
            prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == pid), None) or {
                "id": pid,
                "name": it.get("label", f"ID {pid}"),
                "company_id": it.get("company_id", 0),
                "price": it.get("retail", 0.0),
                "company_name": "",
            }
            row_seed = dict(prod)
            row_seed["price"] = float(it.get("retail", row_seed.get("price", 0.0)) or 0.0)
            row_seed["discount_pct"] = float(it.get("pct", row_seed.get("discount_pct", 0.0)) or 0.0)
            row_seed["trade_price"] = float(it.get("trade", row_seed.get("trade_price", 0.0)) or 0.0)
            row_seed["extra_discount_pct"] = float(it.get("extra", row_seed.get("extra_discount_pct", 0.0)) or 0.0)
            row = self._add_product_to_cart(row_seed)
            if row is None:
                continue
            try:
                self.table.cellWidget(row, 1).setValue(float(it.get("retail", 0.0)))
                self.table.cellWidget(row, 2).setValue(float(it.get("pct", 0.0)))
                trade_val = float(it.get("trade", 0.0))
                self.table.item(row, 3).setText(f"{trade_val:.2f}")
                self.table.cellWidget(row, 4).setValue(float(it.get("extra", 0.0)))
                self.table.cellWidget(row, 5).setValue(int(it.get("qty", 1)))
                self._recalc_row(row)
            except Exception:
                pass
        self._recalc_totals()

    def _hold_sale(self):
        if self._edit_transaction_id is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Invoice Edit",
                "Finish or cancel invoice editing before holding a sale.",
            )
            return
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Empty", "No items to hold.")
            return
        snap = self._snapshot_cart()
        default_name = f"Hold {datetime.now().strftime('%H:%M:%S')}"
        name = self._prompt_hold_name(default_name)
        if name is None:
            return
        snap["name"] = (name or "").strip() or default_name
        try:
            saved = self._with_loader("Saving hold...", lambda: self.api.held_sale_new(snap))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        if isinstance(saved, dict) and str(saved.get("detail", "")).strip():
            QtWidgets.QMessageBox.information(self, "Hold Sale", str(saved.get("detail", "")).strip())
            return
        self._load_held_sales()
        self._clear_cart()
        QtWidgets.QMessageBox.information(self, "Held", f"Sale held as \"{snap['name']}\".")

    def _prompt_hold_name(self, default_name: str):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Hold Sale")
        v = QtWidgets.QVBoxLayout(dlg)
        apply_page_layout(v)
        prompt = QtWidgets.QLabel("Name this hold:")
        name_edit = QtWidgets.QLineEdit()
        name_edit.setPlaceholderText("Hold name")
        name_edit.setText(default_name)
        v.addWidget(prompt)
        v.addWidget(name_edit)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        save_btn = QtWidgets.QPushButton("Save Hold")
        set_secondary(cancel_btn)
        set_accent(save_btn)
        cancel_btn.clicked.connect(dlg.reject)
        save_btn.clicked.connect(dlg.accept)
        name_edit.returnPressed.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        v.addLayout(btn_row)
        polish_controls(dlg)
        fit_dialog_to_contents(dlg, min_width=420, fixed=True)
        QtCore.QTimer.singleShot(0, lambda: (name_edit.setFocus(), name_edit.selectAll()))
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return None
        return name_edit.text()

    def _resume_sale(self):
        if self._edit_transaction_id is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Invoice Edit",
                "Finish or cancel invoice editing before resuming a held sale.",
            )
            return
        # Ensure product cache is fresh for stock checks
        self._load_products_cache()
        try:
            loaded = self._with_loader("Loading held sales...", self._load_held_sales)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        if not loaded:
            QtWidgets.QMessageBox.warning(self, "Hold Sale", "Could not load held sales from database.")
            return
        if not self.held_sales:
            QtWidgets.QMessageBox.information(self, "None", "No held sales.")
            return
        max_dlg_w, max_dlg_h = dialog_screen_limits(width_ratio=0.90, height_ratio=0.82, fallback_width=960, fallback_height=700)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Resume Sale")
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        listw = QtWidgets.QListWidget()
        listw.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        listw.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        listw.setWordWrap(False)
        listw.setUniformItemSizes(True)
        rows = list(enumerate(self.held_sales))
        rows.sort(key=lambda it: str((it[1] or {}).get("created", "")), reverse=True)
        if not rows:
            QtWidgets.QMessageBox.information(self, "None", "No held sales.")
            return

        row_h = 32
        chrome_h = 170
        max_rows_fit = max(1, int((max_dlg_h - chrome_h) / max(1, row_h)))
        visible_rows = rows[:max_rows_fit]
        hidden_count = max(0, len(rows) - len(visible_rows))
        fm = listw.fontMetrics()
        list_text_w = fm.horizontalAdvance("Resume Sale") + 24
        for idx, snap in visible_rows:
            label = snap.get("name", f"Hold {idx+1}")
            ts = snap.get("created", "")
            ts_display = ts
            if ts:
                try:
                    parsed_ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    ts_display = parsed_ts.strftime("%d-%m-%Y %H:%M:%S")
                except Exception:
                    try:
                        parsed_ts = datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S")
                        ts_display = parsed_ts.strftime("%d-%m-%Y %H:%M:%S")
                    except Exception:
                        ts_display = str(ts)
            cnt = len(snap.get("items", []))
            text = f"{label} ({cnt} items) {ts_display}"
            list_text_w = max(list_text_w, fm.horizontalAdvance(text) + 24)
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, idx)
            listw.addItem(item)
        if listw.count() > 0:
            listw.setCurrentRow(0)
        list_w = min(max_dlg_w - 24, max(420, list_text_w))
        list_h = listw.frameWidth() * 2 + (listw.count() * row_h) + 4
        listw.setFixedSize(list_w, list_h)
        v.addWidget(listw)
        if hidden_count > 0:
            overflow_lbl = QtWidgets.QLabel(
                f"Showing latest {len(visible_rows)} of {len(rows)} held sales to fit screen without scrolling."
            )
            overflow_lbl.setObjectName("mutedLabel")
            v.addWidget(overflow_lbl)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        ok_btn = btns.button(QtWidgets.QDialogButtonBox.Ok)
        cancel_btn = btns.button(QtWidgets.QDialogButtonBox.Cancel)
        if ok_btn is not None:
            ok_btn.setText("Resume")
            set_accent(ok_btn)
        if cancel_btn is not None:
            set_secondary(cancel_btn)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        v.addWidget(btns)
        polish_controls(dlg)
        fit_dialog_to_contents(dlg, min_width=min(max_dlg_w, list_w + 20), fixed=True, width_ratio=0.90, height_ratio=0.82)
        listw.itemActivated.connect(lambda _item: dlg.accept())
        listw.itemDoubleClicked.connect(lambda _item: dlg.accept())
        QtCore.QTimer.singleShot(0, lambda: listw.setFocus())
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        sel = listw.currentItem()
        if not sel:
            return
        idx = int(sel.data(QtCore.Qt.UserRole))
        selected_snap = self.held_sales[idx]
        hold_id = int(selected_snap.get("id", 0) or 0)
        # If user switches holds while cart has items, park current cart back into holds.
        if self.table.rowCount() > 0:
            parked = self._snapshot_cart()
            parked["name"] = f"Hold {datetime.now().strftime('%H:%M:%S')}"
            try:
                parked_res = self._with_loader("Saving current cart as hold...", lambda: self.api.held_sale_new(parked))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return
            if isinstance(parked_res, dict) and str(parked_res.get("detail", "")).strip():
                QtWidgets.QMessageBox.information(self, "Hold Sale", str(parked_res.get("detail", "")).strip())
                return
        if hold_id <= 0:
            QtWidgets.QMessageBox.warning(self, "Hold Sale", "Selected held sale is invalid.")
            return
        try:
            del_res = self._with_loader("Resuming held sale...", lambda: self.api.held_sale_delete(hold_id))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        if isinstance(del_res, dict) and str(del_res.get("detail", "")).strip():
            QtWidgets.QMessageBox.information(self, "Hold Sale", str(del_res.get("detail", "")).strip())
            return
        self._load_cart_from_snapshot(selected_snap)

    def _with_loader(self, message: str, fn, *args, **kwargs):
        dlg = QtWidgets.QProgressDialog(message, None, 0, 0, self)
        dlg.setWindowTitle("Please wait")
        dlg.setCancelButton(None)
        dlg.setWindowModality(QtCore.Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.show()
        QtWidgets.QApplication.processEvents()
        try:
            return fn(*args, **kwargs)
        finally:
            dlg.close()
            QtWidgets.QApplication.processEvents()

    def _recalc_totals(self):
        total_items = 0
        for r in range(self.table.rowCount()):
            try:
                qty_w = self.table.cellWidget(r, 5)
                total_items += int(qty_w.value()) if isinstance(qty_w, QtWidgets.QSpinBox) else 0
            except Exception:
                pass

        # Subtotal
        subtotal = 0.0
        for r in range(self.table.rowCount()):
            try:
                subtotal += float(self.table.item(r, 6).text() or 0.0)
            except Exception:
                pass
        # Discount (global)
        discount_pct = float(self.discount.value() or 0.0)
        discounted = subtotal * (1.0 - discount_pct / 100.0)
        # VAT
        vat_amount = discounted * (self.vat_percent / 100.0)
        grand = discounted + vat_amount
        try:
            payment_input = float(self.paid_spin.value() or 0.0)
        except Exception:
            payment_input = 0.0
        existing_paid = float(self._edit_existing_paid or 0.0) if self._edit_transaction_id is not None else 0.0
        paid_amount = existing_paid + payment_input
        due_amount = max(0.0, grand - paid_amount)
        self.subtotal_label.setText(f"{subtotal:.2f} ({total_items} item{'s' if total_items != 1 else ''})")
        self.vat_label.setText(f"{vat_amount:.2f} ({self.vat_percent:.2f}%)")
        self.total_label.setText(f"{grand:.2f}")
        self.paid_prior_value_label.setText(f"{existing_paid:.2f}")
        self.paid_total_value_label.setText(f"{paid_amount:.2f}")
        self.due_label.setText(f"{due_amount:.2f}")
        for r in range(self.table.rowCount()):
            self._update_row_margin_tag(r)

    # ---------- Checkout ----------
    def checkout(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Empty", "No items in cart.")
            return
        items = []
        for r in range(self.table.rowCount()):
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                pid = int(meta.get("id", 0) or 0)
                qty_w = self.table.cellWidget(r, 5)
                qty = int(qty_w.value()) if isinstance(qty_w, QtWidgets.QSpinBox) else 1
                if pid and qty > 0:
                    retail = float(self.table.cellWidget(r, 1).value() or 0.0)
                    pct = float(self.table.cellWidget(r, 2).value() or 0.0)
                    extra = float(self.table.cellWidget(r, 4).value() or 0.0)
                    trade = float(self.table.item(r, 3).text() or 0.0)
                    unit = trade * (1.0 - (extra / 100.0))
                    items.append(
                        {
                            "id": pid,
                            "quantity": qty,
                            "name": str(meta.get("name", "") or ""),
                            "retail_price": retail,
                            "discount_pct": pct,
                            "extra_discount_pct": extra,
                            "trade_price": trade,
                            "unit_price": unit,
                        }
                    )
            except Exception:
                pass
        if not items:
            QtWidgets.QMessageBox.information(self, "Empty", "No valid items to checkout.")
            return

        try:
            # Totals
            subtotal = 0.0
            for r in range(self.table.rowCount()):
                try:
                    subtotal += float(self.table.item(r, 6).text() or 0.0)
                except Exception:
                    pass
            discount_pct = float(self.discount.value() or 0.0)
            discounted = subtotal * (1.0 - discount_pct / 100.0)
            vat_amount = discounted * (self.vat_percent / 100.0)
            grand = discounted + vat_amount
            payment_input = float(self.paid_spin.value() or 0.0)
            existing_paid = float(self._edit_existing_paid or 0.0) if self._edit_transaction_id is not None else 0.0
            paid_amount = existing_paid + payment_input
            due_amount = max(0.0, grand - paid_amount)
            if paid_amount - grand > 1e-6:
                over = paid_amount - grand
                if self._edit_transaction_id is not None:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Overpayment",
                        (
                            f"Paid amount ({paid_amount:.2f}) exceeds updated invoice total ({grand:.2f}) "
                            f"by {over:.2f}.\nReduce Add Payment or edit payment history."
                        ),
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Overpayment",
                        (
                            f"Paid amount ({paid_amount:.2f}) exceeds invoice total ({grand:.2f}) by {over:.2f}.\n"
                            "Reduce paid amount."
                        ),
                    )
                return

            try:
                cust_id = int(self.customer.currentData() or 0)
            except Exception:
                cust_id = 0

            payload = {
                "customer_id": cust_id,
                "user_id": int(self.user_id or 0),
                "total": grand,
                "paid": paid_amount,
                "discount": discount_pct,
                "items": items,
            }
            if self._edit_transaction_id is not None:
                tx_id = int(self._edit_transaction_id)
                resp = self._with_loader(
                    "Updating invoice...",
                    lambda: self.api.transaction_update(tx_id, payload),
                )
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    raise Exception(str(resp.get("detail")))
                invoice_id = int(resp.get("id", tx_id) or tx_id) if isinstance(resp, dict) else tx_id
                self._print_receipt(
                    items,
                    subtotal,
                    discount_pct,
                    vat_amount,
                    self.vat_percent,
                    grand,
                    invoice_number=invoice_id,
                    paid_amount=paid_amount,
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    f"Invoice #{invoice_id} updated. Added: {payment_input:.2f}, Due: {due_amount:.2f}",
                )
            else:
                resp = self._with_loader("Completing checkout...", lambda: self.api.transaction_new(payload))
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    raise Exception(str(resp.get("detail")))
                invoice_id = int(resp.get("id", 0) or 0) if isinstance(resp, dict) else 0
                self._print_receipt(
                    items,
                    subtotal,
                    discount_pct,
                    vat_amount,
                    self.vat_percent,
                    grand,
                    invoice_number=invoice_id if invoice_id > 0 else None,
                    paid_amount=paid_amount,
                )
                msg = (
                    f"Checkout complete. Invoice #{invoice_id}. Due: {due_amount:.2f}"
                    if invoice_id > 0
                    else f"Checkout complete. Due: {due_amount:.2f}"
                )
                QtWidgets.QMessageBox.information(self, "Success", msg)
            self._load_products_cache()
            self._exit_invoice_edit_mode()
            self._clear_cart()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    # ---------- Receipt ----------
    def _print_receipt(
        self,
        items,
        gross,
        discount_pct,
        vat_amount,
        vat_pct,
        total_with_vat,
        invoice_number=None,
        paid_amount=None,
    ):
        printer = QtPrintSupport.QPrinter()
        try:
            printer.setPageSize(QtPrintSupport.QPrinter.A4)
        except Exception:
            pass
        try:
            printer.setOrientation(QtPrintSupport.QPrinter.Portrait)
        except Exception:
            pass
        try:
            printer.setFullPage(True)
        except Exception:
            pass
        dialog = QtPrintSupport.QPrintDialog(printer, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        cust_name = self.customer.currentText() or "Walk-in"
        try:
            s = self.api.settings_map() or {}
            settings = s.get("settings", {}) or {}
        except Exception:
            settings = {}
        business_name = settings.get("business_name", "PharmaSpot")
        receipt_footer = settings.get("receipt_footer", "Thank you for your purchase!")
        logo_path = settings.get("logo_path", "assets/images/logo.svg")
        logo_pix = QtGui.QPixmap()
        try:
            p = Path(logo_path)
            if not p.is_file():
                p = Path.cwd() / logo_path
            if p.is_file():
                logo_pix.load(str(p))
        except Exception:
            pass

        rows = []
        for it in items:
            try:
                pid = int(it.get("id", 0) or 0)
                # Lookup row to read final unit price
                name = str(pid)
                final_price = 0.0
                qty = int(it.get("quantity", 0) or 0)
                for r in range(self.table.rowCount()):
                    meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                    if int(meta.get("id", 0) or 0) == pid:
                        name = self.table.item(r, 0).text()
                        retail = float(self.table.cellWidget(r, 1).value())
                        pct = float(self.table.cellWidget(r, 2).value())
                        extra = float(self.table.cellWidget(r, 4).value())
                        trade = retail * (1.0 - (pct / 100.0))
                        final_price = trade * (1.0 - (extra / 100.0))
                        break
                line_total = final_price * qty
                rows.append(
                    {
                        "name": str(name),
                        "qty": qty,
                        "unit_price": final_price,
                        "line_total": line_total,
                    }
                )
            except Exception:
                pass
        if not rows:
            rows.append({"name": "No items", "qty": 0, "unit_price": 0.0, "line_total": 0.0, "empty": True})

        now = QtCore.QDateTime.currentDateTime().toString("dd-MM-yyyy hh:mm:ss")
        invoice_ref = f"INV-{int(invoice_number):05d}" if invoice_number else "DRAFT"
        try:
            paid_val = float(total_with_vat if paid_amount is None else paid_amount)
        except Exception:
            paid_val = float(total_with_vat or 0.0)
        due_val = max(0.0, float(total_with_vat or 0.0) - paid_val)
        discounted_subtotal = max(0.0, float(total_with_vat or 0.0) - float(vat_amount or 0.0))
        discount_amount = max(0.0, float(gross or 0.0) - discounted_subtotal)
        due_label = "Amount Due" if due_val > 0.0001 else "Paid in Full"
        due_bg = QtGui.QColor("#0f172a" if due_val > 0.0001 else "#166534")
        business_name = str(business_name or "PharmaSpot")
        receipt_footer = str(receipt_footer or "Thank you for your purchase!")

        painter = QtGui.QPainter()
        if not painter.begin(printer):
            QtWidgets.QMessageBox.critical(self, "Print Error", "Could not start printer drawing.")
            return
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)

            page = printer.paperRect()
            if page.isNull():
                page = printer.pageRect()
            if page.isNull():
                page = QtCore.QRect(0, 0, 1240, 1754)

            px_per_mm = max(1.0, float(page.width()) / 210.0)  # A4 width in mm
            margin_px = int(px_per_mm * 8.0)  # fixed 8mm margin
            x0 = page.left() + margin_px
            y0 = page.top() + margin_px
            content_w = page.width() - (margin_px * 2)
            content_h = page.height() - (margin_px * 2)
            bottom = y0 + content_h

            line_pen = QtGui.QPen(QtGui.QColor("#E5E7EB"), 1)
            soft_text = QtGui.QColor("#6B7280")
            main_text = QtGui.QColor("#111827")

            def font(size: int, bold: bool = False):
                f = QtGui.QFont("Segoe UI", size)
                f.setBold(bold)
                return f

            def wrapped_height(fnt: QtGui.QFont, text: str, width: int) -> int:
                fm = QtGui.QFontMetrics(fnt)
                rect = fm.boundingRect(0, 0, max(1, int(width)), 10000, QtCore.Qt.TextWordWrap, str(text))
                return max(rect.height(), fm.height())

            inner_pad = max(2, int(content_w * 0.002))
            left = x0 + inner_pad
            right = x0 + content_w - inner_pad
            y = y0 + inner_pad
            inner_w = right - left

            # Header
            left_w = int(inner_w * 0.64)
            right_w = inner_w - left_w
            logo_h = 0
            if not logo_pix.isNull():
                logo_target_h = 52
                logo_target_w = int(left_w * 0.34)
                scaled = logo_pix.scaled(
                    logo_target_w,
                    logo_target_h,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
                painter.drawPixmap(left, y, scaled)
                logo_h = scaled.height() + 8

            painter.setPen(main_text)
            painter.setFont(font(20, True))
            business_h = wrapped_height(painter.font(), business_name, left_w)
            painter.drawText(
                QtCore.QRect(left, y + logo_h, left_w, business_h + 4),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop | QtCore.Qt.TextWordWrap,
                business_name,
            )

            painter.setPen(soft_text)
            painter.setFont(font(11))
            painter.drawText(
                QtCore.QRect(left, y + logo_h + business_h + 4, left_w, 24),
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                "Sales Invoice",
            )

            meta_x = left + left_w
            meta_label_w = int(right_w * 0.36)
            meta_value_w = right_w - meta_label_w - 8
            meta_rows = [
                ("Invoice #", invoice_ref),
                ("Date", now),
                ("Customer", str(cust_name or "Walk-in")),
            ]
            line_h = 24
            for i, (label, value) in enumerate(meta_rows):
                ly = y + (i * line_h)
                painter.setPen(soft_text)
                painter.setFont(font(10))
                painter.drawText(
                    QtCore.QRect(meta_x, ly, meta_label_w, line_h),
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                    f"{label}:",
                )
                painter.setPen(main_text)
                painter.setFont(font(11, True))
                painter.drawText(
                    QtCore.QRect(meta_x + meta_label_w + 8, ly, meta_value_w, line_h),
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                    str(value),
                )

            header_h = max(logo_h + business_h + 34, len(meta_rows) * line_h + 8)
            y += header_h + 10
            painter.setPen(line_pen)
            painter.drawLine(left, y, right, y)
            y += 10

            # Items table
            item_w = int(inner_w * 0.56)
            qty_w = int(inner_w * 0.10)
            unit_w = int(inner_w * 0.17)
            line_w = inner_w - item_w - qty_w - unit_w
            row_x = [left, left + item_w, left + item_w + qty_w, left + item_w + qty_w + unit_w, right]

            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor("#F3F4F6"))
            painter.drawRect(left, y, inner_w, 30)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(line_pen)
            painter.drawRect(left, y, inner_w, 30)
            painter.setPen(main_text)
            painter.setFont(font(10, True))
            painter.drawText(QtCore.QRect(row_x[0] + 6, y, item_w - 12, 30), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, "ITEM")
            painter.drawText(QtCore.QRect(row_x[1] + 4, y, qty_w - 8, 30), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, "QTY")
            painter.drawText(QtCore.QRect(row_x[2] + 4, y, unit_w - 8, 30), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, "UNIT PRICE")
            painter.drawText(QtCore.QRect(row_x[3] + 4, y, line_w - 8, 30), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, "LINE TOTAL")
            y += 30

            painter.setFont(font(11))
            for row in rows:
                if row.get("empty"):
                    row_h = 30
                else:
                    row_h = max(32, wrapped_height(painter.font(), str(row.get("name", "")), item_w - 12) + 10)

                if y + row_h > bottom - 220:
                    break

                painter.setPen(line_pen)
                painter.drawLine(left, y + row_h, right, y + row_h)
                painter.setPen(main_text)
                painter.drawText(
                    QtCore.QRect(row_x[0] + 6, y + 4, item_w - 12, row_h - 8),
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.TextWordWrap,
                    str(row.get("name", "")),
                )
                if not row.get("empty"):
                    painter.drawText(
                        QtCore.QRect(row_x[1] + 4, y, qty_w - 8, row_h),
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                        str(int(row.get("qty", 0) or 0)),
                    )
                    painter.drawText(
                        QtCore.QRect(row_x[2] + 4, y, unit_w - 8, row_h),
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                        f"{float(row.get('unit_price', 0.0) or 0.0):.2f}",
                    )
                    painter.setFont(font(11, True))
                    painter.drawText(
                        QtCore.QRect(row_x[3] + 4, y, line_w - 8, row_h),
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                        f"{float(row.get('line_total', 0.0) or 0.0):.2f}",
                    )
                    painter.setFont(font(11))
                y += row_h

            # Summary
            y += 12
            sum_w = int(inner_w * 0.42)
            sum_x = right - sum_w
            k_w = int(sum_w * 0.62)
            v_w = sum_w - k_w
            summary_rows = [
                (f"Gross:", f"{gross:.2f}", False),
                (f"Discount ({discount_pct:.2f}%):", f"-{discount_amount:.2f}", False),
                (f"VAT ({vat_pct:.2f}%):", f"+{vat_amount:.2f}", False),
                ("Paid:", f"{paid_val:.2f}", True),
            ]
            painter.setFont(font(11))
            for label, value, bold in summary_rows:
                painter.setPen(soft_text if not bold else main_text)
                painter.setFont(font(11, bold))
                painter.drawText(QtCore.QRect(sum_x, y, k_w - 8, 24), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, label)
                painter.setPen(main_text)
                painter.drawText(QtCore.QRect(sum_x + k_w, y, v_w, 24), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, value)
                y += 24

            painter.setPen(QtGui.QPen(QtGui.QColor("#CBD5E1"), 1))
            painter.drawLine(sum_x, y + 2, sum_x + sum_w, y + 2)
            painter.setPen(main_text)
            painter.setFont(font(13, True))
            painter.drawText(QtCore.QRect(sum_x, y + 6, k_w - 8, 28), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, "Grand Total:")
            painter.drawText(QtCore.QRect(sum_x + k_w, y + 6, v_w, 28), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, f"{total_with_vat:.2f}")
            y += 44

            # Due badge
            badge_text = f"{due_label}: {due_val:.2f}"
            painter.setFont(font(11, True))
            fm = QtGui.QFontMetrics(painter.font())
            badge_w = fm.horizontalAdvance(badge_text) + 26
            badge_h = fm.height() + 10
            badge_x = right - badge_w
            painter.fillRect(QtCore.QRect(badge_x, y, badge_w, badge_h), due_bg)
            painter.setPen(QtGui.QColor("#FFFFFF"))
            painter.drawText(QtCore.QRect(badge_x, y, badge_w, badge_h), QtCore.Qt.AlignCenter, badge_text)
            y += badge_h + 18

            # Footer
            painter.setPen(QtGui.QPen(QtGui.QColor("#CBD5E1"), 1, QtCore.Qt.DashLine))
            painter.drawLine(left, y, right, y)
            painter.setPen(soft_text)
            painter.setFont(font(10))
            painter.drawText(
                QtCore.QRect(left, y + 8, inner_w, 28),
                QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter,
                receipt_footer,
            )
        finally:
            painter.end()

    # ---------- User ----------
    def set_user(self, user: dict):
        try:
            self.user_id = int(user.get("id", 0) or 0)
        except Exception:
            self.user_id = 0

