from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, PushButton, SubtitleLabel

from r6_tactics_board.application.services.editor_session import EditorSessionService
from r6_tactics_board.presentation.styles.theme import (
    item_view_palette,
    page_stylesheet,
    timeline_table_stylesheet,
)
from r6_tactics_board.presentation.widgets.asset_icons import compact_asset_icon, compact_asset_pixmap


class GadgetCountsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("gadget-counts-page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("themePage", True)

        self.session_service = EditorSessionService()
        self._updating = False
        self._table_icon_size = QSize(22, 22)

        self.refresh_button = PushButton("刷新配置")
        self.attack_gadget_table = QTableWidget()
        self.defense_gadget_table = QTableWidget()
        self.attack_ability_table = QTableWidget()
        self.defense_ability_table = QTableWidget()

        self._init_ui()
        self._init_signals()
        self._refresh_data()
        self.refresh_theme()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(SubtitleLabel("数量配置"))
        layout.addWidget(
            BodyLabel(
                "上方分别编辑进攻方与防守方通用道具数量和保留方式。下方分别编辑进攻方与防守方技能道具数量和保留方式。"
            )
        )
        layout.addWidget(self.refresh_button)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)
        top_layout.addLayout(self._build_table_column("进攻方通用道具", self.attack_gadget_table), 1)
        top_layout.addLayout(self._build_table_column("防守方通用道具", self.defense_gadget_table), 1)
        layout.addLayout(top_layout, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)
        bottom_layout.addLayout(self._build_table_column("进攻方技能道具", self.attack_ability_table), 1)
        bottom_layout.addLayout(self._build_table_column("防守方技能道具", self.defense_ability_table), 1)
        layout.addLayout(bottom_layout, 2)

        self._configure_gadget_table(self.attack_gadget_table)
        self._configure_gadget_table(self.defense_gadget_table)
        self._configure_operator_table(self.attack_ability_table)
        self._configure_operator_table(self.defense_ability_table)

    def _build_table_column(self, title: str, table: QTableWidget) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(BodyLabel(title))
        layout.addWidget(table, 1)
        return layout

    def _configure_gadget_table(self, table: QTableWidget) -> None:
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["道具", "保留", "数量"])
        self._configure_table_base(table, row_height=40)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

    def _configure_operator_table(self, table: QTableWidget) -> None:
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["干员 / 技能", "保留", "数量"])
        self._configure_table_base(table, row_height=56)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

    def _configure_table_base(self, table: QTableWidget, row_height: int) -> None:
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setWordWrap(False)
        table.setAlternatingRowColors(False)
        table.setIconSize(self._table_icon_size)
        table.verticalHeader().setDefaultSectionSize(row_height)

    def _init_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_data)

    def _refresh_data(self) -> None:
        self._updating = True
        self._populate_gadget_table(self.attack_gadget_table, "attack")
        self._populate_gadget_table(self.defense_gadget_table, "defense")
        self._populate_operator_ability_table(self.attack_ability_table, "attack")
        self._populate_operator_ability_table(self.defense_ability_table, "defense")
        self._updating = False

    def _populate_gadget_table(self, table: QTableWidget, side: str) -> None:
        entries = self.session_service.list_gadget_assets(side)
        table.setRowCount(len(entries))

        for row, asset in enumerate(entries):
            name_item = QTableWidgetItem(asset.name)
            name_item.setIcon(compact_asset_icon(asset.path, self._table_icon_size))
            name_item.setToolTip(asset.key)
            table.setItem(row, 0, name_item)

            persist_combo = self._create_persist_combo(asset.persists_on_map)
            persist_combo.currentIndexChanged.connect(
                lambda _index, combo=persist_combo, asset_side=asset.side, gadget_key=asset.key: self._save_gadget_persistence(
                    asset_side,
                    gadget_key,
                    bool(combo.itemData(combo.currentIndex())),
                )
            )
            table.setCellWidget(row, 1, persist_combo)

            spin = self._create_count_spinbox(asset.max_count, 0, 10)
            spin.valueChanged.connect(
                lambda value, asset_side=asset.side, gadget_key=asset.key: self._save_gadget_count(
                    asset_side,
                    gadget_key,
                    value,
                )
            )
            table.setCellWidget(row, 2, spin)

    def _populate_operator_ability_table(self, table: QTableWidget, side: str) -> None:
        entries = self.session_service.list_operator_catalog(side)
        table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            ability_name = entry.ability_name or "-"
            table.setCellWidget(
                row,
                0,
                self._create_operator_ability_cell(
                    entry.name or entry.key,
                    ability_name,
                    entry.key,
                    entry.icon_path,
                    entry.ability_icon_path,
                ),
            )

            persist_combo = self._create_persist_combo(entry.ability_persists_on_map)
            persist_combo.currentIndexChanged.connect(
                lambda _index, combo=persist_combo, operator_side=side, operator_key=entry.key: self._save_ability_persistence(
                    operator_side,
                    operator_key,
                    bool(combo.itemData(combo.currentIndex())),
                )
            )
            table.setCellWidget(row, 1, persist_combo)

            spin = self._create_count_spinbox(entry.ability_max_count, 0, 20)
            spin.valueChanged.connect(
                lambda value, operator_side=side, operator_key=entry.key: self._save_ability_count(
                    operator_side,
                    operator_key,
                    value,
                )
            )
            table.setCellWidget(row, 2, spin)

    def _create_operator_ability_cell(
        self,
        operator_name: str,
        ability_name: str,
        operator_key: str,
        operator_icon_path: str,
        ability_icon_path: str,
    ) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(0)

        operator_label = BodyLabel(operator_name)
        operator_label.setToolTip(operator_key)
        ability_label = CaptionLabel(ability_name)
        ability_label.setToolTip(ability_name)
        ability_label.setStyleSheet("color: rgba(140, 140, 140, 0.95);")
        operator_icon = self._create_icon_label(operator_icon_path)
        ability_icon = self._create_icon_label(ability_icon_path)

        layout.addWidget(operator_icon, 0, 0)
        layout.addWidget(operator_label, 0, 1)
        layout.addWidget(ability_icon, 1, 0)
        layout.addWidget(ability_label, 1, 1)
        layout.setColumnStretch(1, 1)
        return widget

    def _create_icon_label(self, icon_path: str) -> QLabel:
        label = QLabel()
        label.setFixedSize(self._table_icon_size)
        pixmap = compact_asset_pixmap(icon_path, self._table_icon_size)
        if not pixmap.isNull():
            label.setPixmap(pixmap)
        return label

    def _create_count_spinbox(self, value: int, minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)
        spin.setValue(value)
        return spin

    def _create_persist_combo(self, persists_on_map: bool) -> ComboBox:
        combo = ComboBox()
        combo.addItem("一次性")
        combo.setItemData(0, False)
        combo.addItem("保留")
        combo.setItemData(1, True)
        combo.setCurrentIndex(1 if persists_on_map else 0)
        return combo

    def _save_gadget_count(self, side: str, gadget_key: str, count: int) -> None:
        if self._updating:
            return
        self.session_service.save_gadget_count(side, gadget_key, count)

    def _save_gadget_persistence(self, side: str, gadget_key: str, persists_on_map: bool) -> None:
        if self._updating:
            return
        self.session_service.save_gadget_persistence(side, gadget_key, persists_on_map)

    def _save_ability_count(self, side: str, operator_key: str, count: int) -> None:
        if self._updating:
            return
        self.session_service.save_operator_ability_count(side, operator_key, count)

    def _save_ability_persistence(self, side: str, operator_key: str, persists_on_map: bool) -> None:
        if self._updating:
            return
        self.session_service.save_operator_ability_persistence(side, operator_key, persists_on_map)

    def refresh_theme(self) -> None:
        self.setStyleSheet(page_stylesheet(self.objectName()))
        table_style = timeline_table_stylesheet()
        palette = item_view_palette()

        for table in (
            self.attack_gadget_table,
            self.defense_gadget_table,
            self.attack_ability_table,
            self.defense_ability_table,
        ):
            table.setStyleSheet(table_style)
            table.setPalette(palette)
            table.viewport().setPalette(palette)
