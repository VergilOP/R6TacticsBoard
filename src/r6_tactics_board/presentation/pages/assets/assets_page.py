from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QListWidget, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton, SubtitleLabel

from r6_tactics_board.infrastructure.assets.asset_paths import (
    ATTACK_OPERATORS_DIR,
    DEFENSE_OPERATORS_DIR,
    MAPS_DIR,
    ensure_asset_directories,
)
from r6_tactics_board.infrastructure.assets.asset_registry import AssetRegistry
from r6_tactics_board.presentation.styles.theme import item_view_palette, list_widget_stylesheet, page_stylesheet


class AssetsPage(QWidget):
    map_requested = pyqtSignal(str)
    operator_requested = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()

        ensure_asset_directories()
        self.asset_registry = AssetRegistry()

        self.refresh_button = PushButton()
        self.maps_path_label = BodyLabel()
        self.attack_path_label = BodyLabel()
        self.defense_path_label = BodyLabel()
        self.maps_count_label = BodyLabel()
        self.attack_count_label = BodyLabel()
        self.defense_count_label = BodyLabel()
        self.maps_list = QListWidget()
        self.attack_list = QListWidget()
        self.defense_list = QListWidget()

        self.setObjectName("assets-page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("themePage", True)
        self._init_ui()
        self._init_signals()
        self._refresh_summary()
        self.refresh_theme()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(SubtitleLabel("资源管理"))
        layout.addWidget(
            BodyLabel(
                "双击地图可直接加载整张地图资源，双击干员图标可在编辑区快速创建干员节点。"
            )
        )

        self.refresh_button.setText("刷新资源统计")
        layout.addWidget(self.refresh_button)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        grid.addWidget(BodyLabel("地图目录"), 0, 0)
        grid.addWidget(self.maps_path_label, 0, 1)
        grid.addWidget(self.maps_count_label, 0, 2)

        grid.addWidget(BodyLabel("进攻干员目录"), 1, 0)
        grid.addWidget(self.attack_path_label, 1, 1)
        grid.addWidget(self.attack_count_label, 1, 2)

        grid.addWidget(BodyLabel("防守干员目录"), 2, 0)
        grid.addWidget(self.defense_path_label, 2, 1)
        grid.addWidget(self.defense_count_label, 2, 2)

        layout.addLayout(grid)

        lists_layout = QHBoxLayout()
        lists_layout.addLayout(self._build_list_column("地图", self.maps_list))
        lists_layout.addLayout(self._build_list_column("进攻干员图标", self.attack_list))
        lists_layout.addLayout(self._build_list_column("防守干员图标", self.defense_list))
        layout.addLayout(lists_layout)
        layout.addStretch(1)

    def _build_list_column(self, title: str, widget: QListWidget) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.addWidget(BodyLabel(title))
        layout.addWidget(widget)
        return layout

    def _init_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_summary)
        self.maps_list.itemDoubleClicked.connect(self._on_map_double_clicked)
        self.attack_list.itemDoubleClicked.connect(lambda item: self._on_operator_double_clicked(item, "attack"))
        self.defense_list.itemDoubleClicked.connect(lambda item: self._on_operator_double_clicked(item, "defense"))

    def _refresh_summary(self) -> None:
        ensure_asset_directories()

        map_assets = self.asset_registry.list_map_assets()
        attack_assets = self.asset_registry.list_operator_assets("attack")
        defense_assets = self.asset_registry.list_operator_assets("defense")

        self.maps_path_label.setText(str(MAPS_DIR))
        self.attack_path_label.setText(str(ATTACK_OPERATORS_DIR))
        self.defense_path_label.setText(str(DEFENSE_OPERATORS_DIR))

        self.maps_count_label.setText(f"{len(map_assets)} 张地图")
        self.attack_count_label.setText(f"{len(attack_assets)} 个图标")
        self.defense_count_label.setText(f"{len(defense_assets)} 个图标")

        self._fill_map_list(map_assets)
        self._fill_operator_list(self.attack_list, attack_assets)
        self._fill_operator_list(self.defense_list, defense_assets)

    def _fill_map_list(self, map_assets) -> None:
        self.maps_list.clear()
        if not map_assets:
            self.maps_list.addItem("(空)")
            return

        for asset in map_assets:
            item = QListWidgetItem(asset.name)
            item.setToolTip(asset.path)
            item.setData(0x0100, asset.path)
            self.maps_list.addItem(item)

    def _fill_operator_list(self, widget: QListWidget, assets) -> None:
        widget.clear()
        if not assets:
            widget.addItem("(空)")
            return

        for asset in assets:
            item = QListWidgetItem(asset.key)
            item.setData(0x0100, asset.key)
            widget.addItem(item)

    def _on_map_double_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(0x0100)
        if path:
            self.map_requested.emit(path)

    def _on_operator_double_clicked(self, item: QListWidgetItem, side: str) -> None:
        operator_key = item.data(0x0100)
        if operator_key:
            self.operator_requested.emit(side, operator_key)

    def refresh_theme(self) -> None:
        self.setStyleSheet(page_stylesheet(self.objectName()))
        list_style = list_widget_stylesheet()
        palette = item_view_palette()
        self.maps_list.setStyleSheet(list_style)
        self.attack_list.setStyleSheet(list_style)
        self.defense_list.setStyleSheet(list_style)
        for widget in (self.maps_list, self.attack_list, self.defense_list):
            widget.setPalette(palette)
            widget.viewport().setPalette(palette)
