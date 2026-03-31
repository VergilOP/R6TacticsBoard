from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SubtitleLabel, Theme, isDarkTheme

from r6_tactics_board.infrastructure.diagnostics.debug_logging import debug_log

from r6_tactics_board.presentation.styles.theme import (
    apply_theme,
    is_theme_change_event,
    page_stylesheet,
    popup_combo_stylesheet,
)


class ThemeComboBox(QComboBox):
    def refresh_theme(self) -> None:
        self.setStyleSheet(popup_combo_stylesheet())


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._syncing_theme_combo = False
        self._pending_theme: Theme | None = None
        self.theme_combo = ThemeComboBox()
        self.setObjectName("settings-page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("themePage", True)
        self._init_ui()
        self._init_signals()
        self._sync_theme_combo()
        self.refresh_theme()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(BodyLabel("主题风格"))

        self.theme_combo.addItem("深色")
        self.theme_combo.setItemData(0, Theme.DARK)
        self.theme_combo.addItem("浅色")
        self.theme_combo.setItemData(1, Theme.LIGHT)
        row.addWidget(self.theme_combo, 1)

        layout.addWidget(SubtitleLabel("设置"))
        layout.addWidget(BodyLabel("默认主题为深色，可在这里切换应用的主题风格。"))
        layout.addLayout(row)
        layout.addStretch(1)

    def _init_signals(self) -> None:
        self.theme_combo.activated.connect(self._apply_theme)

    def _apply_theme(self, index: int) -> None:
        if self._syncing_theme_combo:
            return
        theme = self.theme_combo.itemData(index)
        if theme is not None:
            debug_log(f"settings: apply theme request={theme}")
            self._pending_theme = theme
            QTimer.singleShot(0, self._apply_pending_theme)

    def _apply_pending_theme(self) -> None:
        theme = self._pending_theme
        self._pending_theme = None
        if theme is None:
            return
        debug_log(f"settings: apply theme commit={theme}")
        apply_theme(theme, save=True, lazy=True)
        debug_log(f"settings: apply theme done={theme}")

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if is_theme_change_event(event):
            self._sync_theme_combo()

    def _sync_theme_combo(self) -> None:
        self._syncing_theme_combo = True
        self.theme_combo.setCurrentIndex(0 if isDarkTheme() else 1)
        self._syncing_theme_combo = False

    def refresh_theme(self) -> None:
        self.setStyleSheet(page_stylesheet(self.objectName()))
        self.theme_combo.refresh_theme()
