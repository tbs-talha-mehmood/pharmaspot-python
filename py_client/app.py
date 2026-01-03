from PyQt5 import QtWidgets
from api import ApiClient
from views.login import LoginView
from views.shell import ShellView


class PharmaApp(QtWidgets.QStackedWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api

        self.login = LoginView(self.api, on_success=self._on_login)
        self.shell = ShellView(self.api)

        self.addWidget(self.login)
        self.addWidget(self.shell)
        self.setCurrentWidget(self.login)

    def _on_login(self, user: dict):
        self.shell.set_user(user)
        self.setCurrentWidget(self.shell)

