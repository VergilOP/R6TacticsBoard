from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, LineEdit, PrimaryPushButton, PushButton, SubtitleLabel

from r6_tactics_board.domain.models import MapInteractionPoint, MapInteractionType, Point2D
from r6_tactics_board.infrastructure.assets.asset_registry import AssetRegistry, MapAsset
from r6_tactics_board.presentation.widgets.canvas.map_debug_scene import MapDebugScene
from r6_tactics_board.presentation.widgets.canvas.map_view import MapView


class DebugPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.asset_registry = AssetRegistry()
        self._syncing_panel = False
        self._current_map_asset: MapAsset | None = None
        self._current_floor_key = ""
        self._current_interaction_id = ""
        self._interactions: list[MapInteractionPoint] = []
        self._linked_floor_boxes: dict[str, QCheckBox] = {}

        self.map_combo = ComboBox()
        self.load_map_button = PrimaryPushButton("加载地图")
        self.save_button = PushButton("保存地图元数据")
        self.place_button = PushButton("放置互动点")
        self.floor_combo = ComboBox()
        self.map_status_label = BodyLabel("当前地图：未加载")
        self.map_view = MapView()
        self.kind_combo = ComboBox()
        self.source_floor_combo = ComboBox()
        self.bidirectional_box = QCheckBox("双向联通")
        self.label_edit = LineEdit()
        self.note_edit = LineEdit()
        self.position_label = BodyLabel("-")
        self.selected_label = BodyLabel("当前互动点：无")
        self.linked_floors_container = QWidget()
        self.linked_floors_layout = QVBoxLayout(self.linked_floors_container)
        self.delete_button = PushButton("删除互动点")
        self.debug_hint = BodyLabel(
            "楼梯建议设置为双向联通，并会在联通楼层显示；舱口默认只在源楼层显示。"
        )

        self._init_ui()
        self._init_signals()
        self._reload_map_registry()
        self._refresh_property_panel()

    def _init_ui(self) -> None:
        self.map_view.setScene(MapDebugScene())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        center_layout = QVBoxLayout()
        center_layout.setSpacing(16)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(12)
        toolbar_layout.addWidget(BodyLabel("地图"))
        toolbar_layout.addWidget(self.map_combo, 1)
        toolbar_layout.addWidget(self.load_map_button)
        toolbar_layout.addWidget(BodyLabel("楼层"))
        toolbar_layout.addWidget(self.floor_combo)
        toolbar_layout.addWidget(self.place_button)
        toolbar_layout.addWidget(self.save_button)

        center_layout.addLayout(toolbar_layout)
        center_layout.addWidget(self.map_status_label)
        center_layout.addWidget(self.map_view, 1)

        side_panel = QVBoxLayout()
        side_panel.setSpacing(12)

        property_grid = QGridLayout()
        property_grid.setHorizontalSpacing(12)
        property_grid.setVerticalSpacing(12)

        self.place_button.setCheckable(True)
        self.label_edit.setPlaceholderText("例如：主楼梯、VIP 舱口")
        self.note_edit.setPlaceholderText("补充说明，可为空")
        self.kind_combo.addItem("楼梯")
        self.kind_combo.setItemData(0, MapInteractionType.STAIRS.value)
        self.kind_combo.addItem("舱口")
        self.kind_combo.setItemData(1, MapInteractionType.HATCH.value)

        self.linked_floors_layout.setContentsMargins(0, 0, 0, 0)
        self.linked_floors_layout.setSpacing(6)

        property_grid.addWidget(BodyLabel("类型"), 0, 0)
        property_grid.addWidget(self.kind_combo, 0, 1)
        property_grid.addWidget(BodyLabel("源楼层"), 1, 0)
        property_grid.addWidget(self.source_floor_combo, 1, 1)
        property_grid.addWidget(BodyLabel("坐标"), 2, 0)
        property_grid.addWidget(self.position_label, 2, 1)
        property_grid.addWidget(BodyLabel("标签"), 3, 0)
        property_grid.addWidget(self.label_edit, 3, 1)
        property_grid.addWidget(BodyLabel("备注"), 4, 0)
        property_grid.addWidget(self.note_edit, 4, 1)

        side_panel.addWidget(SubtitleLabel("地图 Debug"))
        side_panel.addWidget(
            BodyLabel("用于编辑地图级互动点元数据，为楼梯、舱口等后续上下楼逻辑打基础。")
        )
        side_panel.addWidget(self.selected_label)
        side_panel.addLayout(property_grid)
        side_panel.addWidget(self.bidirectional_box)
        side_panel.addWidget(BodyLabel("联通楼层"))
        side_panel.addWidget(self.linked_floors_container)
        side_panel.addWidget(self.debug_hint)
        side_panel.addWidget(self.delete_button)
        side_panel.addStretch(1)

        layout.addLayout(center_layout, 1)
        layout.addLayout(side_panel)

    def _init_signals(self) -> None:
        self.load_map_button.clicked.connect(self._load_selected_map)
        self.save_button.clicked.connect(self._save_map_metadata)
        self.place_button.toggled.connect(self._set_place_mode)
        self.floor_combo.currentIndexChanged.connect(self._switch_floor_from_combo)
        self.kind_combo.currentIndexChanged.connect(self._apply_kind_change)
        self.source_floor_combo.currentIndexChanged.connect(self._apply_source_floor_change)
        self.bidirectional_box.toggled.connect(self._apply_bidirectional_change)
        self.label_edit.editingFinished.connect(self._apply_label_change)
        self.note_edit.editingFinished.connect(self._apply_note_change)
        self.delete_button.clicked.connect(self._delete_selected_interaction)

        scene = self._scene()
        if scene is not None:
            scene.interaction_selected.connect(self._select_interaction)
            scene.interaction_moved.connect(self._move_interaction)
            scene.interaction_place_requested.connect(self._create_interaction_at)

    def _reload_map_registry(self) -> None:
        assets = self.asset_registry.list_map_assets()
        self.map_combo.blockSignals(True)
        self.map_combo.clear()
        for index, asset in enumerate(assets):
            self.map_combo.addItem(asset.name)
            self.map_combo.setItemData(index, asset.path)
        self.map_combo.blockSignals(False)

    def _load_selected_map(self) -> None:
        map_path = self.map_combo.currentData()
        if not map_path:
            return
        self.load_map_from_path(str(map_path))

    def load_map_from_path(self, map_path: str) -> None:
        asset = self.asset_registry.load_map_asset(map_path)
        scene = self._scene()
        if asset is None or scene is None or not asset.floors:
            return

        self._current_map_asset = asset
        self._interactions = deepcopy(asset.interactions)
        self._current_floor_key = asset.floors[0].key
        self._current_interaction_id = ""

        self._reload_floor_combos()
        self._load_current_floor_image(fit_view=True)
        self._refresh_property_panel()

    def _reload_floor_combos(self) -> None:
        floors = self._current_map_asset.floors if self._current_map_asset is not None else []

        self.floor_combo.blockSignals(True)
        self.source_floor_combo.blockSignals(True)
        self.floor_combo.clear()
        self.source_floor_combo.clear()
        for index, floor in enumerate(floors):
            self.floor_combo.addItem(floor.name)
            self.floor_combo.setItemData(index, floor.key)
            self.source_floor_combo.addItem(floor.name)
            self.source_floor_combo.setItemData(index, floor.key)
            if floor.key == self._current_floor_key:
                self.floor_combo.setCurrentIndex(index)
        self.floor_combo.blockSignals(False)
        self.source_floor_combo.blockSignals(False)
        self._rebuild_linked_floor_boxes()

    def _load_current_floor_image(self, fit_view: bool) -> None:
        scene = self._scene()
        if scene is None or self._current_map_asset is None:
            return

        floor = next(
            (item for item in self._current_map_asset.floors if item.key == self._current_floor_key),
            self._current_map_asset.floors[0],
        )
        if not scene.load_map_image(floor.image_path):
            return

        scene.set_floor(self._current_floor_key)
        scene.set_interactions(self._interactions)
        self.map_status_label.setText(f"当前地图：{self._current_map_asset.name} / {floor.name}")
        if fit_view:
            self.map_view.fit_scene()
        scene.select_interaction(self._current_interaction_id or None)

    def _switch_floor_from_combo(self) -> None:
        floor_key = self.floor_combo.currentData()
        if not floor_key:
            return
        self._current_floor_key = str(floor_key)
        if self._current_interaction_id:
            selected = self._find_interaction(self._current_interaction_id)
            if selected is not None and not self._interaction_visible_on_current_floor(selected):
                self._current_interaction_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _set_place_mode(self, enabled: bool) -> None:
        scene = self._scene()
        if scene is not None:
            scene.set_place_mode(enabled)
        self.place_button.setText("放置中" if enabled else "放置互动点")

    def _create_interaction_at(self, x: float, y: float) -> None:
        if self._current_map_asset is None:
            return

        kind = MapInteractionType(self.kind_combo.currentData() or MapInteractionType.STAIRS.value)
        interaction = MapInteractionPoint(
            id=self._next_interaction_id(),
            kind=kind,
            position=Point2D(x=x, y=y),
            floor_key=self._current_floor_key or "default",
            linked_floor_keys=self._default_linked_floors(self._current_floor_key, kind),
            is_bidirectional=kind == MapInteractionType.STAIRS,
        )
        self._interactions.append(interaction)
        self._current_interaction_id = interaction.id
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _move_interaction(self, interaction_id: str, x: float, y: float) -> None:
        interaction = self._find_interaction(interaction_id)
        if interaction is None:
            return
        interaction.position = Point2D(x=x, y=y)
        self._current_interaction_id = interaction_id
        self._refresh_property_panel()

    def _select_interaction(self, interaction_id: str) -> None:
        self._current_interaction_id = interaction_id
        self._refresh_property_panel()

    def _apply_kind_change(self) -> None:
        if self._syncing_panel:
            return
        interaction = self._selected_interaction()
        if interaction is None:
            return
        kind = MapInteractionType(self.kind_combo.currentData() or MapInteractionType.STAIRS.value)
        interaction.kind = kind
        if kind == MapInteractionType.STAIRS and not interaction.is_bidirectional:
            interaction.is_bidirectional = True
        if kind == MapInteractionType.HATCH and interaction.is_bidirectional:
            interaction.is_bidirectional = False
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _apply_source_floor_change(self) -> None:
        if self._syncing_panel:
            return
        interaction = self._selected_interaction()
        if interaction is None:
            return
        floor_key = self.source_floor_combo.currentData()
        if not floor_key:
            return
        interaction.floor_key = str(floor_key)
        interaction.linked_floor_keys = [
            item for item in interaction.linked_floor_keys if item != interaction.floor_key
        ]
        self._rebuild_linked_floor_boxes()
        if not self._interaction_visible_on_current_floor(interaction):
            self._current_interaction_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _apply_bidirectional_change(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        interaction = self._selected_interaction()
        if interaction is None:
            return
        interaction.is_bidirectional = checked
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _apply_label_change(self) -> None:
        interaction = self._selected_interaction()
        if interaction is None:
            return
        interaction.label = self.label_edit.text().strip()
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _apply_note_change(self) -> None:
        interaction = self._selected_interaction()
        if interaction is None:
            return
        interaction.note = self.note_edit.text().strip()
        self._refresh_property_panel()

    def _delete_selected_interaction(self) -> None:
        interaction = self._selected_interaction()
        if interaction is None:
            return
        self._interactions = [item for item in self._interactions if item.id != interaction.id]
        self._current_interaction_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _save_map_metadata(self) -> None:
        if self._current_map_asset is None:
            return
        self.asset_registry.save_map_interactions(self._current_map_asset.path, self._interactions)
        self._current_map_asset = self.asset_registry.load_map_asset(self._current_map_asset.path)
        if self._current_map_asset is not None:
            self.map_status_label.setText(
                f"当前地图：{self._current_map_asset.name} / {self._current_floor_key} · 已保存"
            )

    def _refresh_property_panel(self) -> None:
        interaction = self._selected_interaction()
        self._syncing_panel = True

        if interaction is None:
            self.selected_label.setText("当前互动点：无")
            self.position_label.setText("-")
            self.label_edit.setText("")
            self.note_edit.setText("")
            self.bidirectional_box.setChecked(False)
            self._rebuild_linked_floor_boxes()
            self._set_property_enabled(False)
            self._syncing_panel = False
            return

        self.selected_label.setText(f"当前互动点：{interaction.id}")
        self.position_label.setText(f"({interaction.position.x:.1f}, {interaction.position.y:.1f})")
        self.label_edit.setText(interaction.label)
        self.note_edit.setText(interaction.note)
        self.bidirectional_box.setChecked(interaction.is_bidirectional)
        self._set_combo_value(self.kind_combo, interaction.kind.value)
        self._set_combo_value(self.source_floor_combo, interaction.floor_key)
        self._set_property_enabled(True)
        self._rebuild_linked_floor_boxes()
        for floor_key, checkbox in self._linked_floor_boxes.items():
            checkbox.setChecked(floor_key in interaction.linked_floor_keys)

        self._syncing_panel = False

    def _set_property_enabled(self, enabled: bool) -> None:
        self.kind_combo.setEnabled(enabled)
        self.source_floor_combo.setEnabled(enabled)
        self.bidirectional_box.setEnabled(enabled)
        self.label_edit.setEnabled(enabled)
        self.note_edit.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        for checkbox in self._linked_floor_boxes.values():
            checkbox.setEnabled(enabled)

    def _rebuild_linked_floor_boxes(self) -> None:
        while self.linked_floors_layout.count():
            item = self.linked_floors_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._linked_floor_boxes.clear()

        if self._current_map_asset is None:
            return

        selected = self._selected_interaction()
        source_floor = selected.floor_key if selected is not None else self._current_floor_key
        for floor in self._current_map_asset.floors:
            if floor.key == source_floor:
                continue
            checkbox = QCheckBox(floor.name)
            checkbox.setProperty("floor_key", floor.key)
            checkbox.toggled.connect(self._apply_linked_floors_change)
            self.linked_floors_layout.addWidget(checkbox)
            self._linked_floor_boxes[floor.key] = checkbox
        self.linked_floors_layout.addStretch(1)

    def _apply_linked_floors_change(self) -> None:
        if self._syncing_panel:
            return
        interaction = self._selected_interaction()
        if interaction is None:
            return
        interaction.linked_floor_keys = [
            floor_key
            for floor_key, checkbox in self._linked_floor_boxes.items()
            if checkbox.isChecked()
        ]
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _selected_interaction(self) -> MapInteractionPoint | None:
        if not self._current_interaction_id:
            return None
        return self._find_interaction(self._current_interaction_id)

    def _find_interaction(self, interaction_id: str) -> MapInteractionPoint | None:
        for item in self._interactions:
            if item.id == interaction_id:
                return item
        return None

    def _interaction_visible_on_current_floor(self, interaction: MapInteractionPoint) -> bool:
        if interaction.floor_key == self._current_floor_key:
            return True
        return interaction.is_bidirectional and self._current_floor_key in interaction.linked_floor_keys

    def _next_interaction_id(self) -> str:
        numbers = []
        for item in self._interactions:
            if item.id.startswith("interaction-"):
                suffix = item.id.removeprefix("interaction-")
                if suffix.isdigit():
                    numbers.append(int(suffix))
        next_id = max(numbers, default=0) + 1
        return f"interaction-{next_id}"

    def _default_linked_floors(self, source_floor: str, kind: MapInteractionType) -> list[str]:
        if self._current_map_asset is None:
            return []
        floor_keys = [item.key for item in self._current_map_asset.floors]
        if source_floor not in floor_keys:
            return []
        index = floor_keys.index(source_floor)
        if kind == MapInteractionType.STAIRS:
            if index + 1 < len(floor_keys):
                return [floor_keys[index + 1]]
            if index - 1 >= 0:
                return [floor_keys[index - 1]]
            return []
        if index - 1 >= 0:
            return [floor_keys[index - 1]]
        return []

    def _scene(self) -> MapDebugScene | None:
        scene = self.map_view.scene()
        if isinstance(scene, MapDebugScene):
            return scene
        return None

    @staticmethod
    def _set_combo_value(combo: ComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
