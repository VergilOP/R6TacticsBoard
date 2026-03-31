import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, qconfig

from r6_tactics_board.infrastructure.diagnostics.debug_logging import (
    install_qfluent_theme_debug_logging,
    install_runtime_debug_logging,
)
from r6_tactics_board.presentation.styles.theme import apply_theme


def create_app() -> QApplication:
    install_runtime_debug_logging()
    install_qfluent_theme_debug_logging()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    config_path = Path("config/config.json")
    qconfig.load(config_path, qconfig)
    if config_path.exists():
        apply_theme(qconfig.themeMode.value, save=False, lazy=True)
    else:
        apply_theme(Theme.DARK, save=True, lazy=True)
    return app
