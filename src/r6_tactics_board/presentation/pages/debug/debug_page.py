from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QSpinBox, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, LineEdit, PrimaryPushButton, PushButton, SubtitleLabel

from r6_tactics_board.domain.models import (
    MapInteractionPoint,
    MapInteractionType,
    MapSurface,
    MapSurfaceType,
    Point2D,
)
from r6_tactics_board.infrastructure.assets.asset_registry import AssetRegistry, MapAsset
from r6_tactics_board.presentation.styles.theme import page_stylesheet
from r6_tactics_board.presentation.widgets.canvas.map_debug_scene import MapDebugScene
from r6_tactics_board.presentation.widgets.canvas.map_view import MapView


class DebugPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("debug-page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("themePage", True)
        self.asset_registry = AssetRegistry()
        self._syncing_panel = False
        self._current_map_asset: MapAsset | None = None
        self._current_floor_key = ""
        self._current_interaction_id = ""
        self._current_surface_id = ""
        self._interactions: list[MapInteractionPoint] = []
        self._surfaces: list[MapSurface] = []
        self._linked_floor_boxes: dict[str, QCheckBox] = {}

        self.map_combo = ComboBox()
        self.load_map_button = PrimaryPushButton("加载地图")
        self.save_button = PushButton("保存地图元数据")
        self.place_button = PushButton("开始放置")
        self.place_tool_combo = ComboBox()
        self.snap_distance_spin = QSpinBox()
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
        self.selected_surface_label = BodyLabel("当前可破坏面：无")
        self.linked_floors_container = QWidget()
        self.linked_floors_layout = QVBoxLayout(self.linked_floors_container)
        self.delete_button = PushButton("删除互动点")
        self.delete_surface_button = PushButton("删除可破坏面")
        self.debug_hint = BodyLabel(
            "互动点用于楼层联通；软墙和 Hatch 面用于战术界面的加固与开洞标记。"
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
        toolbar_layout.addWidget(BodyLabel("放置类型"))
        toolbar_layout.addWidget(self.place_tool_combo)
        toolbar_layout.addWidget(BodyLabel("吸附"))
        toolbar_layout.addWidget(self.snap_distance_spin)
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
        self.place_tool_combo.addItem("互动点")
        self.place_tool_combo.setItemData(0, "interaction")
        self.place_tool_combo.setItemText(0, "楼梯")
        self.place_tool_combo.addItem("软墙")
        self.place_tool_combo.setItemData(1, "soft_wall")
        self.place_tool_combo.addItem("Hatch 面")
        self.place_tool_combo.setItemData(2, "hatch_surface")
        self.snap_distance_spin.setRange(0, 40)
        self.snap_distance_spin.setSingleStep(2)
        self.snap_distance_spin.setValue(10)
        self.snap_distance_spin.setSuffix(" px")
        self.snap_distance_spin.setToolTip("0 表示关闭软墙端点吸附")

        self.label_edit.setPlaceholderText("例如：主楼梯 / VIP Hatch")
        self.note_edit.setPlaceholderText("补充说明，可为空")
        self.kind_combo.addItem("楼梯")
        self.kind_combo.setItemData(0, MapInteractionType.STAIRS.value)
        self.kind_combo.addItem("舱口")
        self.kind_combo.setItemData(1, "hatch_surface")

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
            BodyLabel("用于编辑地图级互动点和可破坏面，为战术编辑里的跨层和开洞操作提供元数据。")
        )
        side_panel.addWidget(self.selected_label)
        side_panel.addWidget(self.selected_surface_label)
        side_panel.addLayout(property_grid)
        side_panel.addWidget(self.bidirectional_box)
        side_panel.addWidget(BodyLabel("联通楼层"))
        side_panel.addWidget(self.linked_floors_container)
        side_panel.addWidget(self.debug_hint)
        side_panel.addWidget(self.delete_button)
        side_panel.addWidget(self.delete_surface_button)
        side_panel.addStretch(1)

        layout.addLayout(center_layout, 1)
        layout.addLayout(side_panel)

    def _init_signals(self) -> None:
        self.load_map_button.clicked.connect(self._load_selected_map)
        self.save_button.clicked.connect(self._save_map_metadata)
        self.place_button.toggled.connect(self._set_place_mode)
        self.place_tool_combo.currentIndexChanged.connect(self._on_place_tool_changed)
        self.snap_distance_spin.valueChanged.connect(self._apply_snap_distance)
        self.floor_combo.currentIndexChanged.connect(self._switch_floor_from_combo)
        self.kind_combo.currentIndexChanged.connect(self._apply_kind_change)
        self.source_floor_combo.currentIndexChanged.connect(self._apply_source_floor_change)
        self.bidirectional_box.toggled.connect(self._apply_bidirectional_change)
        self.label_edit.editingFinished.connect(self._apply_label_change)
        self.note_edit.editingFinished.connect(self._apply_note_change)
        self.delete_button.clicked.connect(self._delete_selected_interaction)
        self.delete_surface_button.clicked.connect(self._delete_selected_surface)

        scene = self._scene()
        if scene is not None:
            scene.set_surface_endpoint_snap_distance(self.snap_distance_spin.value())
            scene.interaction_selected.connect(self._select_interaction)
            scene.interaction_moved.connect(self._move_interaction)
            scene.interaction_place_requested.connect(self._create_interaction_at)
            scene.surface_selected.connect(self._select_surface)
            scene.surface_moved.connect(self._move_surface)
            scene.surface_place_requested.connect(self._create_surface)

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
        self._surfaces = deepcopy(asset.surfaces)
        self._current_floor_key = asset.floors[0].key
        self._current_interaction_id = ""
        self._current_surface_id = ""

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
        scene.set_surfaces(self._surfaces)
        scene.set_interactions(self._interactions)
        self.map_status_label.setText(f"当前地图：{self._current_map_asset.name} / {floor.name}")
        if fit_view:
            self.map_view.fit_scene()
        scene.select_interaction(self._current_interaction_id or None)
        scene.select_surface(self._current_surface_id or None)

    def _switch_floor_from_combo(self) -> None:
        floor_key = self.floor_combo.currentData()
        if not floor_key:
            return
        self._current_floor_key = str(floor_key)
        if self._current_interaction_id:
            selected = self._find_interaction(self._current_interaction_id)
            if selected is not None and not self._interaction_visible_on_current_floor(selected):
                self._current_interaction_id = ""
        if self._current_surface_id:
            selected_surface = self._find_surface(self._current_surface_id)
            if selected_surface is not None and selected_surface.floor_key != self._current_floor_key:
                self._current_surface_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _set_place_mode(self, enabled: bool) -> None:
        scene = self._scene()
        if scene is not None:
            scene.set_place_mode(str(self.place_tool_combo.currentData()) if enabled else "")
        self._sync_place_button_label()

    def _apply_snap_distance(self, value: int) -> None:
        scene = self._scene()
        if scene is not None:
            scene.set_surface_endpoint_snap_distance(float(value))

    def _on_place_tool_changed(self) -> None:
        if self.place_button.isChecked():
            self._set_place_mode(True)
            return
        self._sync_place_button_label()

    def _create_interaction_at(self, payload: object) -> None:
        if self._current_map_asset is None:
            return
        points: list[Point2D] = []
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    points.append(Point2D(x=float(item[0]), y=float(item[1])))
        if len(points) < 2:
            return

        kind = MapInteractionType.STAIRS
        interaction = MapInteractionPoint(
            id=self._next_interaction_id(),
            kind=kind,
            position=Point2D(x=points[0].x, y=points[0].y),
            floor_key=self._current_floor_key or "default",
            target_position=Point2D(x=points[-1].x, y=points[-1].y),
            path_points=[Point2D(x=point.x, y=point.y) for point in points[1:-1]],
            linked_floor_keys=self._default_linked_floors(self._current_floor_key, kind),
            is_bidirectional=kind == MapInteractionType.STAIRS,
        )
        self._interactions.append(interaction)
        self._current_interaction_id = interaction.id
        self._current_surface_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _create_surface(self, mode: str, start_x: float, start_y: float, end_x: float, end_y: float) -> None:
        if self._current_map_asset is None:
            return
        kind = MapSurfaceType.SOFT_WALL if mode == "soft_wall" else MapSurfaceType.HATCH
        surface = MapSurface(
            id=self._next_surface_id(),
            kind=kind,
            floor_key=self._current_floor_key or "default",
            start=Point2D(x=start_x, y=start_y),
            end=Point2D(x=end_x, y=end_y),
            linked_floor_keys=(
                self._default_linked_floors(self._current_floor_key, MapInteractionType.HATCH)
                if kind == MapSurfaceType.HATCH
                else []
            ),
            is_bidirectional=False,
        )
        self._surfaces.append(surface)
        self._current_surface_id = surface.id
        self._current_interaction_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _move_interaction(self, interaction_id: str, x: float, y: float) -> None:
        interaction = self._find_interaction(interaction_id)
        if interaction is None:
            return
        dx = x - interaction.position.x
        dy = y - interaction.position.y
        interaction.position = Point2D(x=x, y=y)
        if interaction.target_position is not None:
            interaction.target_position = Point2D(
                x=interaction.target_position.x + dx,
                y=interaction.target_position.y + dy,
            )
        if interaction.path_points:
            interaction.path_points = [
                Point2D(x=point.x + dx, y=point.y + dy)
                for point in interaction.path_points
            ]
        self._current_interaction_id = interaction_id
        self._refresh_property_panel()

    def _move_surface(self, surface_id: str, start_x: float, start_y: float, end_x: float, end_y: float) -> None:
        surface = self._find_surface(surface_id)
        if surface is None:
            return
        surface.start = Point2D(x=start_x, y=start_y)
        surface.end = Point2D(x=end_x, y=end_y)
        self._current_surface_id = surface_id
        self._refresh_property_panel()

    def _select_interaction(self, interaction_id: str) -> None:
        self._current_interaction_id = interaction_id
        self._current_surface_id = ""
        self._refresh_property_panel()

    def _select_surface(self, surface_id: str) -> None:
        self._current_surface_id = surface_id
        self._current_interaction_id = ""
        self._refresh_property_panel()

    def _apply_kind_change(self) -> None:
        if self._syncing_panel:
            return
        interaction = self._selected_interaction()
        if interaction is None:
            return
        kind = MapInteractionType.STAIRS
        interaction.kind = kind
        if not interaction.is_bidirectional:
            interaction.is_bidirectional = True
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _apply_source_floor_change(self) -> None:
        if self._syncing_panel:
            return
        interaction = self._selected_interaction()
        floor_key = self.source_floor_combo.currentData()
        if not floor_key:
            return
        if interaction is not None:
            interaction.floor_key = str(floor_key)
            interaction.linked_floor_keys = [
                item for item in interaction.linked_floor_keys if item != interaction.floor_key
            ]
        else:
            surface = self._selected_surface()
            if surface is None or surface.kind != MapSurfaceType.HATCH:
                return
            surface.floor_key = str(floor_key)
            surface.linked_floor_keys = [
                item for item in surface.linked_floor_keys if item != surface.floor_key
            ]
        self._rebuild_linked_floor_boxes()
        if interaction is not None and not self._interaction_visible_on_current_floor(interaction):
            self._current_interaction_id = ""
        if interaction is None:
            surface = self._selected_surface()
            if surface is not None and surface.floor_key != self._current_floor_key:
                self._current_surface_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _apply_bidirectional_change(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        interaction = self._selected_interaction()
        if interaction is not None:
            interaction.is_bidirectional = checked
        else:
            surface = self._selected_surface()
            if surface is None or surface.kind != MapSurfaceType.HATCH:
                return
            surface.is_bidirectional = checked
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _apply_label_change(self) -> None:
        interaction = self._selected_interaction()
        if interaction is not None:
            interaction.label = self.label_edit.text().strip()
            self._load_current_floor_image(fit_view=False)
            self._refresh_property_panel()
            return
        surface = self._selected_surface()
        if surface is not None:
            surface.label = self.label_edit.text().strip()
            self._load_current_floor_image(fit_view=False)
            self._refresh_property_panel()

    def _apply_note_change(self) -> None:
        interaction = self._selected_interaction()
        if interaction is not None:
            interaction.note = self.note_edit.text().strip()
            self._refresh_property_panel()
            return
        surface = self._selected_surface()
        if surface is not None:
            surface.note = self.note_edit.text().strip()
            self._refresh_property_panel()

    def _delete_selected_interaction(self) -> None:
        interaction = self._selected_interaction()
        if interaction is None:
            return
        self._interactions = [item for item in self._interactions if item.id != interaction.id]
        self._current_interaction_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _delete_selected_surface(self) -> None:
        surface = self._selected_surface()
        if surface is None:
            return
        self._surfaces = [item for item in self._surfaces if item.id != surface.id]
        self._current_surface_id = ""
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _save_map_metadata(self) -> None:
        if self._current_map_asset is None:
            return
        self.asset_registry.save_map_interactions(self._current_map_asset.path, self._interactions)
        self.asset_registry.save_map_surfaces(self._current_map_asset.path, self._surfaces)
        self._current_map_asset = self.asset_registry.load_map_asset(self._current_map_asset.path)
        if self._current_map_asset is not None:
            self.map_status_label.setText(
                f"当前地图：{self._current_map_asset.name} / {self._current_floor_key} / 已保存"
            )

    def _refresh_property_panel(self) -> None:
        interaction = self._selected_interaction()
        surface = self._selected_surface()
        hatch_surface = surface if surface is not None and surface.kind == MapSurfaceType.HATCH else None
        self._syncing_panel = True

        if interaction is None and hatch_surface is None:
            self.selected_label.setText("当前互动点：无")
            self.position_label.setText("-")
            self.label_edit.setText(surface.label if surface is not None else "")
            self.note_edit.setText(surface.note if surface is not None else "")
            self.bidirectional_box.setChecked(False)
            self._rebuild_linked_floor_boxes()
            self._set_property_enabled(False)
        elif interaction is not None:
            self.selected_label.setText(f"当前互动点：{interaction.id}")
            if interaction.kind == MapInteractionType.STAIRS and interaction.target_position is not None:
                self.position_label.setText(
                    f"({interaction.position.x:.1f}, {interaction.position.y:.1f}) -> "
                    f"({interaction.target_position.x:.1f}, {interaction.target_position.y:.1f})"
                )
            else:
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
        else:
            assert hatch_surface is not None
            self.selected_label.setText("当前互动点：无")
            self.position_label.setText(
                f"({hatch_surface.start.x:.1f}, {hatch_surface.start.y:.1f}) -> "
                f"({hatch_surface.end.x:.1f}, {hatch_surface.end.y:.1f})"
            )
            self.label_edit.setText(hatch_surface.label)
            self.note_edit.setText(hatch_surface.note)
            self.bidirectional_box.setChecked(hatch_surface.is_bidirectional)
            self._set_combo_value(self.kind_combo, "hatch_surface")
            self._set_combo_value(self.source_floor_combo, hatch_surface.floor_key)
            self._set_property_enabled(True)
            self.kind_combo.setEnabled(False)
            self._rebuild_linked_floor_boxes()
            for floor_key, checkbox in self._linked_floor_boxes.items():
                checkbox.setChecked(floor_key in hatch_surface.linked_floor_keys)

        if surface is None:
            self.selected_surface_label.setText("当前可破坏面：无")
            self.delete_surface_button.setEnabled(False)
            if interaction is None and hatch_surface is None:
                self.position_label.setText("-")
        else:
            self.selected_surface_label.setText(f"当前可破坏面：{surface.id} ({surface.kind.value})")
            self.position_label.setText(
                f"({surface.start.x:.1f}, {surface.start.y:.1f}) -> ({surface.end.x:.1f}, {surface.end.y:.1f})"
            )
            self.label_edit.setText(surface.label)
            self.note_edit.setText(surface.note)
            self.delete_surface_button.setEnabled(True)

        self._syncing_panel = False

    def _set_property_enabled(self, enabled: bool) -> None:
        self.kind_combo.setEnabled(enabled)
        self.source_floor_combo.setEnabled(enabled)
        self.bidirectional_box.setEnabled(enabled)
        self.delete_button.setEnabled(enabled and self._selected_interaction() is not None)
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
        selected_surface = self._selected_surface()
        source_floor = (
            selected.floor_key
            if selected is not None
            else (
                selected_surface.floor_key
                if selected_surface is not None and selected_surface.kind == MapSurfaceType.HATCH
                else self._current_floor_key
            )
        )
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
        selected_floor_keys = [
            floor_key
            for floor_key, checkbox in self._linked_floor_boxes.items()
            if checkbox.isChecked()
        ]
        if interaction is not None:
            interaction.linked_floor_keys = selected_floor_keys
        else:
            surface = self._selected_surface()
            if surface is None or surface.kind != MapSurfaceType.HATCH:
                return
            surface.linked_floor_keys = selected_floor_keys
        self._load_current_floor_image(fit_view=False)
        self._refresh_property_panel()

    def _selected_interaction(self) -> MapInteractionPoint | None:
        if not self._current_interaction_id:
            return None
        return self._find_interaction(self._current_interaction_id)

    def _selected_surface(self) -> MapSurface | None:
        if not self._current_surface_id:
            return None
        return self._find_surface(self._current_surface_id)

    def _find_interaction(self, interaction_id: str) -> MapInteractionPoint | None:
        for item in self._interactions:
            if item.id == interaction_id:
                return item
        return None

    def _find_surface(self, surface_id: str) -> MapSurface | None:
        for item in self._surfaces:
            if item.id == surface_id:
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

    def _next_surface_id(self) -> str:
        numbers = []
        for item in self._surfaces:
            if item.id.startswith("surface-"):
                suffix = item.id.removeprefix("surface-")
                if suffix.isdigit():
                    numbers.append(int(suffix))
        next_id = max(numbers, default=0) + 1
        return f"surface-{next_id}"

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

    def refresh_theme(self) -> None:
        self.setStyleSheet(page_stylesheet(self.objectName()))
        self.map_view.refresh_theme()

    def _scene(self) -> MapDebugScene | None:
        scene = self.map_view.scene()
        if isinstance(scene, MapDebugScene):
            return scene
        return None

    def _sync_place_button_label(self) -> None:
        if not self.place_button.isChecked():
            self.place_button.setText("开始放置")
            return
        mode = str(self.place_tool_combo.currentData() or "interaction")
        labels = {
            "interaction": "绘制楼梯中（右键完成）",
            "soft_wall": "绘制软墙中",
            "hatch_surface": "绘制 Hatch 面中",
        }
        self.place_button.setText(labels.get(mode, "放置中"))

    @staticmethod
    def _set_combo_value(combo: ComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
