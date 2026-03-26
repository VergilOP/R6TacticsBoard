import sys

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from r6_tactics_board.infrastructure.debug_logging import install_runtime_debug_logging


def create_app() -> QApplication:
    install_runtime_debug_logging()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    setTheme(Theme.DARK)
    return app
