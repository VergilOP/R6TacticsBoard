from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, SubtitleLabel, Theme, setTheme


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.theme_combo = ComboBox()
        self._init_ui()
        self._init_signals()

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
        self.theme_combo.setCurrentIndex(0)
        row.addWidget(self.theme_combo, 1)

        layout.addWidget(SubtitleLabel("设置"))
        layout.addWidget(BodyLabel("默认主题为深色，可在这里切换应用主题风格。"))
        layout.addLayout(row)
        layout.addStretch(1)

    def _init_signals(self) -> None:
        self.theme_combo.currentIndexChanged.connect(self._apply_theme)

    def _apply_theme(self, index: int) -> None:
        theme = self.theme_combo.itemData(index)
        if theme is not None:
            setTheme(theme)
