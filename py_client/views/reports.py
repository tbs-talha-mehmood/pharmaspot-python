from PyQt5 import QtWidgets, QtCore
from datetime import datetime


class ReportsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Reports")
        title.setObjectName("title")
        layout.addWidget(title)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Date From"))
        self.start = QtWidgets.QDateEdit(); self.start.setCalendarPopup(True)
        self.start.setDate(QtCore.QDate.currentDate().addDays(-29))
        row.addWidget(self.start)
        row.addWidget(QtWidgets.QLabel("To"))
        self.end = QtWidgets.QDateEdit(); self.end.setCalendarPopup(True)
        self.end.setDate(QtCore.QDate.currentDate())
        row.addWidget(self.end)
        row.addWidget(QtWidgets.QLabel("User ID"))
        self.user_id = QtWidgets.QSpinBox(); self.user_id.setRange(0, 10**9)
        row.addWidget(self.user_id)
        layout.addLayout(row)

        self.info = QtWidgets.QLabel("")
        layout.addWidget(self.info)

        btn = QtWidgets.QPushButton("Refresh Summary")
        layout.addWidget(btn)
        btn.clicked.connect(self.refresh)
        layout.addStretch(1)

    def refresh(self):
        # Very basic summary using transactions list
        try:
            tx = self.api.transactions_list() or []
        except Exception:
            tx = []
        # filter by date and user
        try:
            start_dt = datetime.strptime(self.start.date().toString('yyyy-MM-dd'), '%Y-%m-%d')
            end_dt = datetime.strptime(self.end.date().toString('yyyy-MM-dd'), '%Y-%m-%d')
        except Exception:
            start_dt = end_dt = None
        uid = int(self.user_id.value())
        out = []
        for t in tx:
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
        count = len(out)
        total = sum(float(t.get("total", 0.0)) for t in out)
        self.info.setText(f"Transactions: {count} | Gross Sales: {total:.2f}")
