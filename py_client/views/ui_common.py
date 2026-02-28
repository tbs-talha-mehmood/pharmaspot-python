from PyQt5 import QtCore, QtWidgets

PAGE_MARGIN = 16
PAGE_SPACING = 12
BUTTON_HEIGHT = 34
INPUT_HEIGHT = 32


def apply_page_layout(layout: QtWidgets.QLayout):
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(PAGE_SPACING)


def apply_header_layout(layout: QtWidgets.QLayout):
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)


def apply_form_layout(form: QtWidgets.QFormLayout):
    form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
    form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)


def configure_table(table: QtWidgets.QTableWidget, *, stretch_last: bool = True):
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    if stretch_last:
        table.horizontalHeader().setStretchLastSection(True)


def dialog_screen_limits(
    *,
    width_ratio: float = 0.92,
    height_ratio: float = 0.90,
    fallback_width: int = 1180,
    fallback_height: int = 760,
):
    screen = QtWidgets.QApplication.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        return (
            max(360, int(geo.width() * width_ratio)),
            max(240, int(geo.height() * height_ratio)),
        )
    return fallback_width, fallback_height


def fit_dialog_to_contents(
    dialog: QtWidgets.QDialog,
    *,
    min_width: int = 0,
    min_height: int = 0,
    width_ratio: float = 0.92,
    height_ratio: float = 0.90,
    fixed: bool = True,
):
    max_w, max_h = dialog_screen_limits(width_ratio=width_ratio, height_ratio=height_ratio)
    dialog.adjustSize()
    target_w = min(max_w, max(int(min_width), dialog.sizeHint().width()))
    target_h = min(max_h, max(int(min_height), dialog.sizeHint().height()))
    if fixed:
        dialog.setFixedSize(target_w, target_h)
    else:
        dialog.resize(target_w, target_h)
    return target_w, target_h


def set_secondary(*buttons: QtWidgets.QPushButton):
    for btn in buttons:
        btn.setProperty("secondary", True)


def set_danger(*buttons: QtWidgets.QPushButton):
    for btn in buttons:
        btn.setProperty("danger", True)


def set_accent(*buttons: QtWidgets.QPushButton):
    for btn in buttons:
        btn.setProperty("accent", True)


def polish_controls(root: QtWidgets.QWidget):
    for btn in root.findChildren(QtWidgets.QPushButton):
        if btn.minimumHeight() < BUTTON_HEIGHT:
            btn.setMinimumHeight(BUTTON_HEIGHT)

    for line in root.findChildren(QtWidgets.QLineEdit):
        if line.minimumHeight() < INPUT_HEIGHT:
            line.setMinimumHeight(INPUT_HEIGHT)

    for combo in root.findChildren(QtWidgets.QComboBox):
        if combo.minimumHeight() < INPUT_HEIGHT:
            combo.setMinimumHeight(INPUT_HEIGHT)

    for spin in root.findChildren(QtWidgets.QSpinBox):
        if spin.minimumHeight() < INPUT_HEIGHT:
            spin.setMinimumHeight(INPUT_HEIGHT)

    for dspin in root.findChildren(QtWidgets.QDoubleSpinBox):
        if dspin.minimumHeight() < INPUT_HEIGHT:
            dspin.setMinimumHeight(INPUT_HEIGHT)

    for date in root.findChildren(QtWidgets.QDateEdit):
        if date.minimumHeight() < INPUT_HEIGHT:
            date.setMinimumHeight(INPUT_HEIGHT)
        date.setAlignment(QtCore.Qt.AlignCenter)
