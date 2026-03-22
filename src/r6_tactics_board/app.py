import sys

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme


def create_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    setTheme(Theme.DARK)
    return app
