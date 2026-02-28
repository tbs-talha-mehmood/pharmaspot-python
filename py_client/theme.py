from __future__ import annotations

from PyQt5 import QtGui, QtWidgets

try:
    import qdarktheme
except Exception:
    qdarktheme = None


DARK_THEME_COLORS = {
    "[dark]": {
        "primary": "#62a0ff",
        "background": "#14171d",
        "background>panel": "#1b212b",
        "background>popup": "#202631",
        "background>table": "#151922",
        "background>textarea": "#171b24",
        "border": "#2f3745",
        "foreground": "#e7edf8",
        "statusBar.background": "#1a1f27",
        "table.alternateBackground": "#ffffff0e",
        "list.alternateBackground": "#ffffff0b",
        "primary>table.selectionBackground": "#62a0ff7f",
        "primary>table.inactiveSelectionBackground": "#62a0ff4f",
        "primary>list.selectionBackground": "#62a0ff66",
        "primary>list.inactiveSelectionBackground": "#62a0ff40",
        "primary>textarea.selectionBackground": "#62a0ff66",
    }
}


APP_QSS = """
QLabel { background: transparent; }
QLabel#title { font-size: 20px; font-weight: 700; color: #f4f8ff; }
QLabel#mutedLabel { color: #b7cae4; font-weight: 600; background: transparent; }
QLabel#moneyStrong { font-size: 22px; font-weight: 700; color: #f8fbff; }
QLabel#error { color: #fca5a5; font-weight: 600; }
QLineEdit#invoiceInput { min-width: 180px; }
QComboBox#posCustomerField {
    min-height: 36px;
    font-size: 14px;
    color: #f1f7ff;
    font-weight: 500;
}
QLineEdit#invoiceInput {
    min-height: 36px;
    font-size: 14px;
    color: #f1f7ff;
    font-weight: 500;
}
QLineEdit#posCustomerInput {
    font-size: 14px;
    color: #f1f7ff;
    font-weight: 500;
}
QComboBox#posCustomerField QAbstractItemView {
    background: #1b2230;
    border: 1px solid #43556f;
    border-radius: 8px;
    color: #eef5ff;
    selection-background-color: rgba(98, 160, 255, 0.36);
    selection-color: #f7fbff;
}
QLineEdit#mainSearchInput {
    min-height: 40px;
    padding: 8px 12px;
    font-size: 14px;
    border: 1px solid #4a6184;
}
QLineEdit#mainSearchInput:focus {
    border: 1px solid #7db2ff;
}
QDateEdit {
    min-height: 32px;
    padding: 2px 8px;
}
QDateEdit::up-button, QDateEdit::down-button {
    width: 18px;
}
QDateEdit QLineEdit {
    padding: 0;
    margin: 0;
}

QListWidget#searchResultsPopup {
    background: #1b2230;
    border: 1px solid #43556f;
    border-radius: 8px;
    padding: 4px;
}
QListWidget#searchResultsPopup::item {
    padding: 6px 8px;
    border-radius: 6px;
}
QListWidget#searchResultsPopup::item:hover {
    background: rgba(98, 160, 255, 0.2);
}
QListWidget#searchResultsPopup::item:selected {
    background: rgba(98, 160, 255, 0.36);
    color: #f7fbff;
}

QFrame#posTopCard, QGroupBox#totalsCard {
    background: #1b212b;
    border: 1px solid #2f3745;
    border-radius: 12px;
}
QGroupBox#totalsCard { margin-top: 8px; padding: 4px 10px; }
QGroupBox#totalsCard::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }

QListWidget#sideNav {
    background: #171b23;
    border-right: 1px solid #2f3745;
    padding-top: 6px;
    outline: 0;
    selection-background-color: transparent;
}
QListWidget#sideNav::item {
    padding: 10px 12px;
    margin: 2px 8px;
    border: none;
    border-radius: 8px;
    outline: none;
}
QListWidget#sideNav::item:hover { background: rgba(98, 160, 255, 0.16); }
QListWidget#sideNav::item:selected,
QListWidget#sideNav::item:selected:active,
QListWidget#sideNav::item:selected:!active {
    background: rgba(98, 160, 255, 0.32);
    color: #f4f8ff;
    border: none;
    font-weight: 700;
    outline: none;
}

QFrame#loginShell {
    background: transparent;
}
QFrame#loginCard {
    background: #1b212b;
    border: 1px solid #2f3745;
    border-radius: 14px;
}
QLabel#loginTitle {
    font-size: 24px;
    font-weight: 700;
    color: #f5f9ff;
}
QLabel#loginSubtitle {
    color: #b7cae4;
    font-size: 13px;
    font-weight: 500;
}
QLineEdit#loginInput {
    min-height: 36px;
    font-size: 14px;
}
QPushButton#loginButton {
    min-height: 40px;
    font-size: 14px;
}

QPushButton {
    font-weight: 400;
    outline: none;
}
QPushButton:focus,
QPushButton:focus:pressed,
QPushButton:default {
    outline: none;
}

QPushButton[secondary="true"] {
    background: #1f2937;
    color: #d8e4f8;
    border: 1px solid #334155;
}
QPushButton[secondary="true"]:hover { background: #273445; }
QPushButton[secondary="true"]:pressed { background: #1a2533; }
QPushButton[secondary="true"]:focus {
    background: #1f2937;
    border: 1px solid #334155;
}

QPushButton[danger="true"] {
    background: #462126;
    color: #fecaca;
    border: 1px solid #7f1d1d;
}
QPushButton[danger="true"]:hover { background: #55272d; }
QPushButton[danger="true"]:pressed { background: #3a1b1f; }
QPushButton[danger="true"]:focus {
    background: #462126;
    border: 1px solid #7f1d1d;
}

QPushButton[accent="true"] {
    background: #62a0ff;
    color: #071323;
    border: 1px solid #6fa8ff;
    padding: 8px 18px;
    font-size: 14px;
    font-weight: 400;
}
QPushButton[accent="true"]:hover { background: #75adff; }
QPushButton[accent="true"]:pressed { background: #4d8ff8; }
QPushButton[accent="true"]:focus {
    background: #62a0ff;
    border: 1px solid #6fa8ff;
}

QPushButton#posActionBtn {
    min-width: 108px;
}
QPushButton#checkoutBtn {
    min-width: 136px;
    min-height: 44px;
    padding: 10px 20px;
    font-size: 15px;
    font-weight: 400;
    color: #ffffff;
    background: #4f8ff7;
    border: 1px solid #6ea4ff;
    border-radius: 10px;
}
QPushButton#checkoutBtn:hover {
    background: #629bfb;
}
QPushButton#checkoutBtn:pressed {
    background: #407fe8;
}
QPushButton#checkoutBtn:focus {
    background: #4f8ff7;
    border: 1px solid #6ea4ff;
}

QTableWidget::item {
    padding: 4px 8px;
    color: #edf4ff;
}
QTableWidget#posCartTable::item {
    padding: 5px 10px;
    font-size: 14px;
    color: #f4f8ff;
}
QTableWidget QAbstractSpinBox#cartEditor {
    background: #1a2434;
    border: 1px solid #324055;
    border-radius: 6px;
    padding: 2px 8px;
    margin: 1px 2px;
    color: #f2f7ff;
    font-size: 14px;
    font-weight: 600;
}
QTableWidget QAbstractSpinBox#cartEditor QLineEdit {
    background: transparent;
    color: #f7fbff;
    selection-background-color: rgba(98, 160, 255, 0.45);
}
QTableWidget QAbstractSpinBox#cartEditor:focus {
    border: 1px solid #62a0ff;
    background: #172132;
}
QTableWidget QAbstractSpinBox#cartEditor:disabled {
    color: #f2f7ff;
    background: #213047;
    border: 1px solid #3e5475;
}

QSpinBox[overstock_warned="true"] {
    border: 1px solid #fca5a5;
}
QHeaderView::section {
    color: #f5f9ff;
    font-size: 13px;
}
QTableWidget::item:selected, QTableView::item:selected {
    color: #ffffff;
}
"""


FALLBACK_BASE_QSS = """
* { font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; }
QWidget {
    background: #14171d;
    color: #e7edf8;
    selection-background-color: rgba(98, 160, 255, 0.44);
    selection-color: #f7fbff;
}
QMainWindow, QDialog { background: #14171d; }
QToolTip {
    background: #202631;
    color: #edf2ff;
    border: 1px solid #334155;
    padding: 4px 6px;
}

QGroupBox {
    font-weight: 600;
    border: 1px solid #2f3745;
    border-radius: 10px;
    margin-top: 12px;
    padding: 8px 12px;
    background: #1b212b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #f4f8ff;
}

QPushButton {
    background: #223046;
    color: #f4f8ff;
    border: 1px solid #344a66;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 400;
    outline: none;
}
QPushButton:hover { background: #2a3b55; }
QPushButton:pressed { background: #1c2a3e; }
QPushButton:focus,
QPushButton:focus:pressed,
QPushButton:default {
    background: #223046;
    border: 1px solid #344a66;
    outline: none;
}
QPushButton:disabled {
    background: #2a2f39;
    color: #90a1bb;
    border: 1px solid #3a4352;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QDateEdit {
    border: 1px solid #2f3745;
    border-radius: 8px;
    padding: 6px 8px;
    background: #1b2029;
    color: #edf2ff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus, QDateEdit:focus {
    border: 1px solid #62a0ff;
}
QComboBox QAbstractItemView {
    background: #202631;
    border: 1px solid #334155;
    selection-background-color: rgba(98, 160, 255, 0.44);
}

QTabWidget::pane {
    border: 1px solid #2f3745;
    border-radius: 10px;
    background: #171c25;
    top: -1px;
}
QTabBar::tab {
    background: #1b2230;
    color: #d9e6fb;
    border: 1px solid #2f3745;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 7px 12px;
    margin-right: 4px;
}
QTabBar::tab:hover { background: #243043; }
QTabBar::tab:selected {
    background: #2a3a52;
    color: #f4f8ff;
}

QTableWidget, QTableView {
    background: #151922;
    border: 1px solid #2f3745;
    alternate-background-color: rgba(255, 255, 255, 0.06);
    gridline-color: #2f3745;
}
QTableWidget::item:selected, QTableView::item:selected {
    background: rgba(98, 160, 255, 0.5);
}
QHeaderView::section {
    background: #1f2734;
    color: #eff5ff;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #2f3745;
    border-right: 1px solid #2f3745;
    font-weight: 600;
}
QTableCornerButton::section {
    background: #1f2734;
    border: 1px solid #2f3745;
}

QListWidget {
    background: #161b24;
    border: 1px solid #2f3745;
    border-radius: 8px;
    alternate-background-color: rgba(255, 255, 255, 0.04);
}
QListWidget::item:selected { background: rgba(98, 160, 255, 0.44); }

QMenuBar, QMenu {
    background: #1a1f27;
    color: #edf2ff;
    border: 1px solid #2f3745;
}
QMenu::item:selected {
    background: rgba(98, 160, 255, 0.35);
}

QStatusBar {
    background: #1a1f27;
    border-top: 1px solid #2f3745;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #51627a;
    background: #1b2029;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background: #62a0ff;
    border-color: #62a0ff;
}

QScrollBar:vertical {
    background: #161b24;
    width: 12px;
    margin: 0;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #3a4659;
    min-height: 24px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover { background: #4a5c77; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

QCalendarWidget QWidget { alternate-background-color: #151922; }
QCalendarWidget QToolButton {
    color: #edf2ff;
    background: #1f2734;
    border: 1px solid #2f3745;
}
QCalendarWidget QMenu {
    background: #202631;
    color: #edf2ff;
}
QCalendarWidget QSpinBox {
    background: #1b2029;
    color: #edf2ff;
}
QCalendarWidget QAbstractItemView:enabled {
    color: #edf2ff;
    background-color: #171b24;
    selection-background-color: rgba(98, 160, 255, 0.44);
    selection-color: #f7fbff;
}
"""


def prepare_theme():
    if qdarktheme is None:
        return
    try:
        qdarktheme.enable_hi_dpi()
    except Exception:
        pass


def apply_theme(app: QtWidgets.QApplication):
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Segoe UI", 10))

    if qdarktheme is not None:
        try:
            qdarktheme.setup_theme(
                theme="dark",
                custom_colors=DARK_THEME_COLORS,
                additional_qss=APP_QSS,
            )
            return
        except TypeError:
            # Compatibility path for older pyqtdarktheme versions.
            try:
                qss = qdarktheme.load_stylesheet(theme="dark") + APP_QSS
                app.setStyleSheet(qss)
                return
            except Exception:
                pass
        except Exception:
            pass

    app.setStyleSheet(FALLBACK_BASE_QSS + APP_QSS)
