from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    Slider,
    SubtitleLabel,
)

from r6_tactics_board.domain.models import Keyframe, MapInfo, OperatorState, Point2D, TacticProject, Timeline
from r6_tactics_board.infrastructure.asset_registry import AssetRegistry
from r6_tactics_board.infrastructure.project_store import ProjectStore
from r6_tactics_board.presentation.widgets.map_scene import MapScene
from r6_tactics_board.presentation.widgets.map_view import MapView
from r6_tactics_board.presentation.widgets.operator_item import OperatorItem
from r6_tactics_board.presentation.widgets.timeline_widget import TimelineWidget


@dataclass(slots=True)
class EditorHistoryState:
    map_path: str
    scene_states: list[OperatorState]
    selected_operator_id: str
    operator_order: list[str]
    operator_labels: dict[str, str]
    keyframe_columns: list[dict[str, OperatorState]]
    current_keyframe_index: int
    current_timeline_row: int
    transition_duration_ms: int


class EditorPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._syncing_panel = False
        self._applying_timeline = False
        self._is_playing = False
        self._history_lock = False
        self._rotation_history_snapshot: EditorHistoryState | None = None
        self._playback_from_column = -1
        self._playback_to_column = -1
        self._playback_elapsed_ms = 0
        self._transition_duration_ms = 700
        self._playback_start_states: dict[str, OperatorState] = {}
        self._playback_end_states: dict[str, OperatorState] = {}
        self._undo_stack: list[EditorHistoryState] = []
        self._redo_stack: list[EditorHistoryState] = []
        self._history_limit = 100
        self._clean_snapshot: EditorHistoryState | None = None

        self.operator_order: list[str] = []
        self.operator_labels: dict[str, str] = {}
        self.keyframe_columns: list[dict[str, OperatorState]] = [{}]
        self.current_keyframe_index = 0
        self.current_timeline_row = -1
        self.current_project_path = ""

        self.project_store = ProjectStore()
        self.asset_registry = AssetRegistry()
        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(16)

        self.map_view = MapView()
        self.timeline = TimelineWidget()
        self.undo_button = PushButton("撤销")
        self.redo_button = PushButton("重做")
        self.open_project_button = PushButton("打开工程")
        self.save_project_button = PushButton("保存工程")
        self.load_map_button = PrimaryPushButton("加载地图")
        self.add_operator_button = PushButton("添加干员")
        self.reset_view_button = PushButton("重置视图")
        self.delete_operator_button = PushButton("删除选中干员")
        self.map_status_label = BodyLabel("当前地图：未加载")
        self.property_title = SubtitleLabel("属性面板")
        self.property_hint = BodyLabel("选中干员后，可在这里编辑名称、阵营、图标、朝向和显示模式。")
        self.selection_label = BodyLabel("当前选中：无")
        self.name_edit = LineEdit()
        self.side_combo = ComboBox()
        self.operator_combo = ComboBox()
        self.rotation_slider = Slider(Qt.Orientation.Horizontal)
        self.rotation_value_label = BodyLabel("0°")
        self.display_mode_combo = ComboBox()
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)

        self._init_ui()
        self._init_signals()
        self._sync_operator_registry()
        self._refresh_property_panel()
        self._refresh_timeline()
        self._reset_history()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        center_layout = QVBoxLayout()
        center_layout.setSpacing(16)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(12)
        toolbar_layout.addWidget(self.undo_button)
        toolbar_layout.addWidget(self.redo_button)
        toolbar_layout.addWidget(self.open_project_button)
        toolbar_layout.addWidget(self.save_project_button)
        toolbar_layout.addWidget(self.load_map_button)
        toolbar_layout.addWidget(self.add_operator_button)
        toolbar_layout.addWidget(self.reset_view_button)
        toolbar_layout.addWidget(self.map_status_label, 1)

        center_layout.addLayout(toolbar_layout)
        center_layout.addWidget(self.map_view, 1)
        center_layout.addWidget(self.timeline)

        side_panel = QVBoxLayout()
        side_panel.setSpacing(12)

        property_grid = QGridLayout()
        property_grid.setHorizontalSpacing(12)
        property_grid.setVerticalSpacing(12)

        self.name_edit.setPlaceholderText("输入自定义名称")
        self.rotation_slider.setRange(0, 359)

        self.side_combo.addItem("进攻")
        self.side_combo.setItemData(0, "attack")
        self.side_combo.addItem("防守")
        self.side_combo.setItemData(1, "defense")

        self.display_mode_combo.addItem("干员图标")
        self.display_mode_combo.setItemData(0, OperatorItem.ICON)
        self.display_mode_combo.addItem("自定义名")
        self.display_mode_combo.setItemData(1, OperatorItem.CUSTOM_NAME)

        property_grid.addWidget(BodyLabel("名称"), 0, 0)
        property_grid.addWidget(self.name_edit, 0, 1)
        property_grid.addWidget(BodyLabel("阵营"), 1, 0)
        property_grid.addWidget(self.side_combo, 1, 1)
        property_grid.addWidget(BodyLabel("图标"), 2, 0)
        property_grid.addWidget(self.operator_combo, 2, 1)
        property_grid.addWidget(BodyLabel("朝向"), 3, 0)
        property_grid.addWidget(self.rotation_slider, 3, 1)
        property_grid.addWidget(BodyLabel("角度"), 4, 0)
        property_grid.addWidget(self.rotation_value_label, 4, 1)
        property_grid.addWidget(BodyLabel("显示模式"), 5, 0)
        property_grid.addWidget(self.display_mode_combo, 5, 1)

        side_panel.addWidget(self.property_title)
        side_panel.addWidget(self.property_hint)
        side_panel.addWidget(self.selection_label)
        side_panel.addLayout(property_grid)
        side_panel.addWidget(self.delete_operator_button)
        side_panel.addStretch(1)

        layout.addLayout(center_layout, 1)
        layout.addLayout(side_panel)

    def _init_signals(self) -> None:
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        self.undo_shortcut.activated.connect(self.undo)
        self.redo_shortcut.activated.connect(self.redo)
        self.load_map_button.clicked.connect(self._load_map)
        self.open_project_button.clicked.connect(self._open_project)
        self.save_project_button.clicked.connect(self._save_project)
        self.add_operator_button.clicked.connect(self._add_operator)
        self.reset_view_button.clicked.connect(self.map_view.reset_view)
        self.delete_operator_button.clicked.connect(self._delete_selected_operator)
        self.name_edit.editingFinished.connect(self._apply_name_edit)
        self.side_combo.currentIndexChanged.connect(self._update_selected_side)
        self.operator_combo.currentIndexChanged.connect(self._update_selected_operator_asset)
        self.rotation_slider.sliderPressed.connect(self._on_rotation_slider_pressed)
        self.rotation_slider.sliderReleased.connect(self._on_rotation_slider_released)
        self.rotation_slider.valueChanged.connect(self._update_selected_rotation)
        self.display_mode_combo.currentIndexChanged.connect(self._update_display_mode)

        self.timeline.add_keyframe_requested.connect(self._add_keyframe_column)
        self.timeline.insert_keyframe_requested.connect(self._insert_keyframe_column)
        self.timeline.duplicate_keyframe_requested.connect(self._duplicate_keyframe_column)
        self.timeline.delete_keyframe_requested.connect(self._delete_current_keyframe_column)
        self.timeline.capture_requested.connect(self._capture_selected_operator_to_current_cell)
        self.timeline.capture_column_requested.connect(self._capture_all_operators_to_current_column)
        self.timeline.clear_cell_requested.connect(self._clear_current_cell)
        self.timeline.previous_column_requested.connect(self._go_to_previous_column)
        self.timeline.next_column_requested.connect(self._go_to_next_column)
        self.timeline.play_requested.connect(self._start_column_playback)
        self.timeline.pause_requested.connect(self._pause_column_playback)
        self.timeline.duration_changed.connect(self._set_transition_duration)
        self.timeline.cell_selected.connect(self._select_timeline_cell)
        self.playback_timer.timeout.connect(self._advance_playback)

        scene = self._map_scene()
        if scene is not None:
            scene.selectionChanged.connect(self._on_scene_selection_changed)
            scene.operator_move_finished.connect(self._on_operator_move_finished)

    def _load_map(self) -> None:
        if not self.confirm_discard_changes("加载地图"):
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择地图图片",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if file_path:
            self._load_map_file(file_path)

    def _load_map_file(self, file_path: str) -> None:
        scene = self._map_scene()
        if scene is None:
            return
        before = self._capture_history_state()
        if scene.load_map_image(file_path):
            self._pause_column_playback()
            self.map_status_label.setText(f"当前地图：{Path(file_path).name}")
            self.map_view.fit_scene()
            self._refresh_property_panel()
            self._commit_history(before)

    def load_map_from_path(self, file_path: str) -> None:
        self._load_map_file(file_path)

    def _open_project(self) -> None:
        if not self.confirm_discard_changes("打开工程"):
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开工程",
            "",
            "R6 Tactics Project (*.r6tb.json)",
        )
        if not file_path:
            return

        project = self.project_store.load(file_path)
        self._apply_project(project)
        self.current_project_path = file_path
        self._reset_history()

    def _save_project(self) -> None:
        self._save_project_to_current_path()

    def _save_project_to_current_path(self) -> bool:
        file_path = self.current_project_path
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存工程",
                "",
                "R6 Tactics Project (*.r6tb.json)",
            )
        if not file_path:
            return False
        if not file_path.endswith(".r6tb.json"):
            file_path += ".r6tb.json"

        self.project_store.save(file_path, self._build_project())
        self.current_project_path = file_path
        self._clean_snapshot = self._capture_history_state()
        self._update_dirty_state()
        return True

    def _add_operator(self) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        before = self._capture_history_state()
        self._pause_column_playback()
        operator = scene.add_operator(self.map_view.scene_center())
        scene.select_operator(operator)
        self._update_operator_icon(operator)
        self._sync_operator_registry()
        self.current_timeline_row = self._operator_row(operator.operator_id)
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def add_operator_from_asset(self, side: str, operator_key: str) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        before = self._capture_history_state()
        self._pause_column_playback()
        operator = scene.add_operator(self.map_view.scene_center())
        operator.set_side(side)
        operator.set_operator_key(operator_key)
        self._update_operator_icon(operator)
        scene.select_operator(operator)
        self._sync_operator_registry()
        self.current_timeline_row = self._operator_row(operator.operator_id)
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _delete_selected_operator(self) -> None:
        operator = self._current_operator()
        scene = self._map_scene()
        if scene is None or operator is None:
            return

        dialog = MessageBox("删除干员", f"确定删除干员 {operator.operator_id} 吗？", self)
        dialog.yesButton.setText("确定")
        dialog.cancelButton.setText("取消")
        if not dialog.exec():
            return

        before = self._capture_history_state()
        self._pause_column_playback()
        operator_id = operator.operator_id
        if scene.delete_selected_operator():
            self._remove_operator_from_timeline(operator_id)
            self._sync_operator_registry()
            self._refresh_property_panel()
            self._refresh_timeline()
            self._commit_history(before)

    def _refresh_property_panel(self) -> None:
        operator = self._current_operator()

        self._syncing_panel = True
        if operator is None:
            self.selection_label.setText("当前选中：无")
            self.name_edit.setText("")
            self.side_combo.setCurrentIndex(0)
            self._refresh_operator_combo("attack")
            self.rotation_slider.setValue(0)
            self.rotation_value_label.setText("0°")
            self.display_mode_combo.setCurrentIndex(0)
            self._set_property_enabled(False)
        else:
            self.selection_label.setText(f"当前选中：干员 {operator.operator_id}")
            self.name_edit.setText(operator.custom_name)
            self.side_combo.setCurrentIndex(0 if operator.side == "attack" else 1)
            self._refresh_operator_combo(operator.side, operator.operator_key)
            self.rotation_slider.setValue(int(operator.rotation()) % 360)
            self.rotation_value_label.setText(f"{int(operator.rotation()) % 360}°")
            self.display_mode_combo.setCurrentIndex(
                0 if operator.display_mode == OperatorItem.ICON else 1
            )
            self._set_property_enabled(True)
        self._syncing_panel = False

    def _set_property_enabled(self, enabled: bool) -> None:
        self.name_edit.setEnabled(enabled)
        self.side_combo.setEnabled(enabled)
        self.operator_combo.setEnabled(enabled)
        self.rotation_slider.setEnabled(enabled)
        self.display_mode_combo.setEnabled(enabled)
        self.delete_operator_button.setEnabled(enabled)

    def _apply_name_edit(self) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        if operator is None:
            return
        if self.name_edit.text() == operator.custom_name:
            return
        before = self._capture_history_state()
        operator.set_custom_name(self.name_edit.text())
        self.operator_labels[operator.operator_id] = operator.custom_name
        self._capture_selected_operator_to_current_cell(refresh_history=False)
        self._refresh_timeline()
        self._commit_history(before)

    def _update_selected_side(self, index: int) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        if operator is None:
            return

        side = self.side_combo.itemData(index)
        if side is None or side == operator.side:
            return

        before = self._capture_history_state()
        operator.set_side(side)
        self._refresh_operator_combo(side)
        self._update_operator_icon(operator)
        self._capture_selected_operator_to_current_cell(refresh_history=False)
        self._commit_history(before)

    def _update_selected_operator_asset(self, index: int) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        if operator is None:
            return

        operator_key = self.operator_combo.itemData(index) or ""
        if operator_key == operator.operator_key:
            return
        before = self._capture_history_state()
        operator.set_operator_key(operator_key)
        self._update_operator_icon(operator)
        self._capture_selected_operator_to_current_cell(refresh_history=False)
        self._commit_history(before)

    def _on_rotation_slider_pressed(self) -> None:
        if self._syncing_panel:
            return
        if self._current_operator() is not None:
            self._rotation_history_snapshot = self._capture_history_state()

    def _update_selected_rotation(self, value: int) -> None:
        self.rotation_value_label.setText(f"{value}°")
        if self._syncing_panel:
            return
        operator = self._current_operator()
        if operator is None:
            return
        operator.setRotation(value)
        self._capture_selected_operator_to_current_cell(refresh_history=False)

    def _on_rotation_slider_released(self) -> None:
        if self._syncing_panel or self._rotation_history_snapshot is None:
            return
        self._commit_history(self._rotation_history_snapshot)
        self._rotation_history_snapshot = None

    def _update_display_mode(self, index: int) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        if operator is None:
            return
        mode = self.display_mode_combo.itemData(index)
        if mode is not None and mode != operator.display_mode:
            before = self._capture_history_state()
            operator.set_display_mode(mode)
            self._capture_selected_operator_to_current_cell(refresh_history=False)
            self._commit_history(before)

    def _add_keyframe_column(self) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        self.keyframe_columns.append({})
        self.current_keyframe_index = len(self.keyframe_columns) - 1
        self._refresh_timeline()
        self._commit_history(before)

    def _insert_keyframe_column(self) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        insert_index = min(self.current_keyframe_index + 1, len(self.keyframe_columns))
        self.keyframe_columns.insert(insert_index, {})
        self.current_keyframe_index = insert_index
        self._refresh_timeline()
        self._commit_history(before)

    def _duplicate_keyframe_column(self) -> None:
        self._pause_column_playback()
        if not self.keyframe_columns:
            return
        before = self._capture_history_state()
        duplicate = {
            operator_id: deepcopy(state)
            for operator_id, state in self.keyframe_columns[self.current_keyframe_index].items()
        }
        insert_index = self.current_keyframe_index + 1
        self.keyframe_columns.insert(insert_index, duplicate)
        self.current_keyframe_index = insert_index
        self._refresh_timeline()
        self._commit_history(before)

    def _delete_current_keyframe_column(self) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        if not self.keyframe_columns:
            return
        if len(self.keyframe_columns) == 1:
            self.keyframe_columns = [{}]
            self.current_keyframe_index = 0
            self.current_timeline_row = -1
            self._apply_timeline_column(0)
            self._refresh_timeline()
            self._commit_history(before)
            return

        dialog = MessageBox(
            "删除当前列",
            "确定删除当前关键帧列吗？该列显式记录的内容将被移除。",
            self,
        )
        dialog.yesButton.setText("确定")
        dialog.cancelButton.setText("取消")
        if not dialog.exec():
            return

        del self.keyframe_columns[self.current_keyframe_index]
        self.current_keyframe_index = min(self.current_keyframe_index, len(self.keyframe_columns) - 1)
        self._apply_timeline_column(self.current_keyframe_index)
        self._refresh_timeline()
        self._commit_history(before)

    def _capture_selected_operator_to_current_cell(self, refresh_history: bool = True) -> None:
        if self._applying_timeline:
            return
        operator = self._current_operator()
        if operator is None:
            return
        before = self._capture_history_state() if refresh_history else None
        self._sync_operator_registry()
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        state = self._state_from_operator(operator)
        if state is None:
            return
        self.keyframe_columns[self.current_keyframe_index][operator.operator_id] = state
        self.current_timeline_row = self._operator_row(operator.operator_id)
        self._refresh_timeline()
        if before is not None:
            self._commit_history(before)

    def _capture_all_operators_to_current_column(self) -> None:
        if self._applying_timeline:
            return
        scene = self._map_scene()
        if scene is None or not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        before = self._capture_history_state()
        self._sync_operator_registry()
        for operator_id, state in scene.snapshot_operator_states_dict().items():
            self.keyframe_columns[self.current_keyframe_index][operator_id] = state
        self._refresh_timeline()
        self._commit_history(before)

    def _clear_current_cell(self) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        if not (0 <= self.current_timeline_row < len(self.operator_order)):
            return
        operator_id = self.operator_order[self.current_timeline_row]
        self.keyframe_columns[self.current_keyframe_index].pop(operator_id, None)
        self._refresh_timeline()
        self._apply_timeline_column(self.current_keyframe_index)
        self._commit_history(before)

    def _select_timeline_cell(self, row: int, column: int) -> None:
        self.current_timeline_row = row
        self.current_keyframe_index = column
        self._pause_column_playback()
        self._apply_timeline_column(column)

        if 0 <= row < len(self.operator_order):
            operator_id = self.operator_order[row]
            scene = self._map_scene()
            operator = scene.find_operator(operator_id) if scene is not None else None
            if operator is not None:
                scene.select_operator(operator)

        self._refresh_property_panel()
        self._refresh_timeline()

    def _apply_timeline_column(self, column: int) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        self._applying_timeline = True
        resolved_states: list[OperatorState] = []
        for operator_id in self.operator_order:
            state = self._resolved_state(operator_id, column)
            if state is not None:
                resolved_states.append(deepcopy(state))

        scene.sync_operator_states(resolved_states)
        for operator in scene.operator_items():
            self._update_operator_icon(operator)

        self._sync_operator_registry()
        self._refresh_property_panel()
        self._applying_timeline = False
        self._refresh_timeline()

    def _resolved_state(self, operator_id: str, column: int) -> OperatorState | None:
        for current in range(column, -1, -1):
            state = self.keyframe_columns[current].get(operator_id)
            if state is not None:
                return state
        return None

    def _resolved_state_map(self, column: int) -> dict[str, OperatorState]:
        result: dict[str, OperatorState] = {}
        for operator_id in self.operator_order:
            state = self._resolved_state(operator_id, column)
            if state is not None:
                result[operator_id] = deepcopy(state)
        return result

    def _refresh_timeline(self) -> None:
        operator_labels = [
            f"{operator_id} | {self.operator_labels.get(operator_id, f'干员 {operator_id}')}"
            for operator_id in self.operator_order
        ]
        keyframe_labels = [f"K{index + 1}" for index in range(len(self.keyframe_columns))]
        explicit_cells = {
            (row, column)
            for column, frame in enumerate(self.keyframe_columns)
            for row, operator_id in enumerate(self.operator_order)
            if operator_id in frame
        }
        self.timeline.set_grid(
            operator_labels,
            keyframe_labels,
            explicit_cells,
            self.current_timeline_row,
            self.current_keyframe_index,
            self._is_playing,
        )
        self.undo_button.setEnabled(bool(self._undo_stack))
        self.redo_button.setEnabled(bool(self._redo_stack))
        self._update_dirty_state()

    def _on_scene_selection_changed(self) -> None:
        operator = self._current_operator()
        self.current_timeline_row = self._operator_row(operator.operator_id) if operator else -1
        self._refresh_property_panel()
        self._refresh_timeline()

    def _on_operator_move_finished(self, operator_id: str) -> None:
        before = self._capture_history_state()
        self.current_timeline_row = self._operator_row(operator_id)
        self._capture_selected_operator_to_current_cell(refresh_history=False)
        self._commit_history(before)

    def _go_to_previous_column(self) -> None:
        self._pause_column_playback()
        if self.current_keyframe_index <= 0:
            return
        self.current_keyframe_index -= 1
        self._apply_timeline_column(self.current_keyframe_index)

    def _go_to_next_column(self) -> None:
        self._pause_column_playback()
        if self.current_keyframe_index >= len(self.keyframe_columns) - 1:
            return
        self.current_keyframe_index += 1
        self._apply_timeline_column(self.current_keyframe_index)

    def _start_column_playback(self) -> None:
        if len(self.keyframe_columns) <= 1:
            return
        if self.current_keyframe_index >= len(self.keyframe_columns) - 1:
            self.current_keyframe_index = 0
            self._apply_timeline_column(self.current_keyframe_index)
        self._is_playing = True
        self._start_transition_to_column(self.current_keyframe_index + 1)
        self._refresh_timeline()

    def _pause_column_playback(self) -> None:
        if not self._is_playing:
            return
        self._is_playing = False
        self.playback_timer.stop()
        self._playback_from_column = -1
        self._playback_to_column = -1
        self._playback_elapsed_ms = 0
        self._refresh_timeline()

    def _advance_playback(self) -> None:
        if not self._is_playing or self._playback_to_column < 0:
            return

        scene = self._map_scene()
        if scene is None:
            self._pause_column_playback()
            return

        self._playback_elapsed_ms += self.playback_timer.interval()
        progress = min(self._playback_elapsed_ms / self._transition_duration_ms, 1.0)
        scene.sync_operator_states(self._interpolated_states(progress))
        for operator in scene.operator_items():
            self._update_operator_icon(operator)

        if progress < 1.0:
            return

        self.current_keyframe_index = self._playback_to_column
        self.current_timeline_row = -1
        self._apply_timeline_column(self.current_keyframe_index)
        if self.current_keyframe_index >= len(self.keyframe_columns) - 1:
            self._pause_column_playback()
        else:
            self._start_transition_to_column(self.current_keyframe_index + 1)

    def _start_transition_to_column(self, target_column: int) -> None:
        if target_column >= len(self.keyframe_columns):
            self._pause_column_playback()
            return
        self._playback_from_column = self.current_keyframe_index
        self._playback_to_column = target_column
        self._playback_elapsed_ms = 0
        self._playback_start_states = self._resolved_state_map(self._playback_from_column)
        self._playback_end_states = self._resolved_state_map(self._playback_to_column)
        self.playback_timer.start()

    def _interpolated_states(self, progress: float) -> list[OperatorState]:
        states: list[OperatorState] = []
        for operator_id in self.operator_order:
            end_state = self._playback_end_states.get(operator_id)
            start_state = self._playback_start_states.get(operator_id, end_state)
            if start_state is None and end_state is None:
                continue
            if start_state is None:
                start_state = end_state
            if end_state is None:
                end_state = start_state

            rotation_delta = ((end_state.rotation - start_state.rotation + 180) % 360) - 180
            states.append(
                OperatorState(
                    id=operator_id,
                    operator_key=end_state.operator_key,
                    custom_name=end_state.custom_name,
                    side=end_state.side,
                    position=Point2D(
                        x=start_state.position.x + (end_state.position.x - start_state.position.x) * progress,
                        y=start_state.position.y + (end_state.position.y - start_state.position.y) * progress,
                    ),
                    rotation=start_state.rotation + rotation_delta * progress,
                    display_mode=end_state.display_mode,
                )
            )
        return states

    def _set_transition_duration(self, value: int) -> None:
        self._transition_duration_ms = value

    def _refresh_operator_combo(self, side: str, selected_key: str = "") -> None:
        assets = self.asset_registry.list_operator_assets(side)
        self.operator_combo.blockSignals(True)
        self.operator_combo.clear()
        self.operator_combo.addItem("(未指定)")
        self.operator_combo.setItemData(0, "")

        current_index = 0
        for index, asset in enumerate(assets, start=1):
            self.operator_combo.addItem(asset.key)
            self.operator_combo.setItemData(index, asset.key)
            if asset.key == selected_key:
                current_index = index

        self.operator_combo.setCurrentIndex(current_index)
        self.operator_combo.blockSignals(False)

    def _update_operator_icon(self, operator: OperatorItem) -> None:
        asset = self.asset_registry.find_operator_asset(operator.side, operator.operator_key)
        operator.set_icon_path(asset.path if asset else "")

    def _sync_operator_registry(self) -> None:
        scene = self._map_scene()
        scene_ids: list[str] = []
        if scene is not None:
            for operator in scene.operator_items():
                scene_ids.append(operator.operator_id)
                self.operator_labels[operator.operator_id] = operator.custom_name

        state_ids = {
            operator_id
            for frame in self.keyframe_columns
            for operator_id in frame
        }
        all_ids = sorted(set(scene_ids) | state_ids, key=self._sort_operator_id)
        self.operator_order = all_ids

        for operator_id in list(self.operator_labels):
            if operator_id not in all_ids:
                del self.operator_labels[operator_id]

    def _remove_operator_from_timeline(self, operator_id: str) -> None:
        for frame in self.keyframe_columns:
            frame.pop(operator_id, None)
        self.operator_labels.pop(operator_id, None)

    def _state_from_operator(self, operator: OperatorItem) -> OperatorState | None:
        scene = self._map_scene()
        if scene is None:
            return None
        return scene.snapshot_operator_states_dict().get(operator.operator_id)

    def _build_project(self) -> TacticProject:
        scene = self._map_scene()
        map_info = None
        if scene is not None and scene.current_map_path:
            map_path = Path(scene.current_map_path)
            map_info = MapInfo(key=map_path.stem, name=map_path.name, image_path=str(map_path))

        keyframes = [
            Keyframe(
                time_ms=index * self._transition_duration_ms,
                operator_states=[deepcopy(frame[operator_id]) for operator_id in self.operator_order if operator_id in frame],
            )
            for index, frame in enumerate(self.keyframe_columns)
        ]
        return TacticProject(
            name=Path(self.current_project_path).stem if self.current_project_path else "untitled",
            map_info=map_info,
            timeline=Timeline(keyframes=keyframes),
            operator_order=list(self.operator_order),
            current_keyframe_index=self.current_keyframe_index,
            transition_duration_ms=self._transition_duration_ms,
        )

    def _apply_project(self, project: TacticProject) -> None:
        self._pause_column_playback()
        scene = self._map_scene()
        if scene is None:
            return

        if project.map_info and project.map_info.image_path:
            if scene.load_map_image(project.map_info.image_path):
                self.map_status_label.setText(f"当前地图：{Path(project.map_info.image_path).name}")
                self.map_view.fit_scene()
            else:
                self.map_status_label.setText("当前地图：加载失败")
        else:
            scene.clear_map()
            self.map_status_label.setText("当前地图：未加载")

        self.operator_order = list(project.operator_order)
        self.operator_labels = {}
        self.keyframe_columns = [
            {state.id: deepcopy(state) for state in keyframe.operator_states}
            for keyframe in project.timeline.keyframes
        ] or [{}]
        self.current_keyframe_index = min(project.current_keyframe_index, len(self.keyframe_columns) - 1)
        self.current_timeline_row = -1
        self._transition_duration_ms = project.transition_duration_ms
        self.timeline.duration_slider.setValue(self._transition_duration_ms)

        for frame in self.keyframe_columns:
            for state in frame.values():
                self.operator_labels[state.id] = state.custom_name
                if state.id not in self.operator_order:
                    self.operator_order.append(state.id)

        self._apply_timeline_column(self.current_keyframe_index)
        self._refresh_timeline()

    def _capture_history_state(self) -> EditorHistoryState:
        scene = self._map_scene()
        selected = self._current_operator()
        return EditorHistoryState(
            map_path=scene.current_map_path if scene is not None else "",
            scene_states=deepcopy(scene.snapshot_operator_states() if scene is not None else []),
            selected_operator_id=selected.operator_id if selected is not None else "",
            operator_order=list(self.operator_order),
            operator_labels=dict(self.operator_labels),
            keyframe_columns=deepcopy(self.keyframe_columns),
            current_keyframe_index=self.current_keyframe_index,
            current_timeline_row=self.current_timeline_row,
            transition_duration_ms=self._transition_duration_ms,
        )

    def _commit_history(self, before: EditorHistoryState) -> None:
        if self._history_lock:
            return
        after = self._capture_history_state()
        if before == after:
            return
        self._undo_stack.append(before)
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack = self._undo_stack[-self._history_limit :]
        self._redo_stack.clear()
        self._refresh_timeline()

    def _reset_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._clean_snapshot = self._capture_history_state()
        self._refresh_timeline()

    def undo(self) -> None:
        if not self._undo_stack:
            return
        current = self._capture_history_state()
        snapshot = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_history_state(snapshot)

    def redo(self) -> None:
        if not self._redo_stack:
            return
        current = self._capture_history_state()
        snapshot = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_history_state(snapshot)

    def _restore_history_state(self, snapshot: EditorHistoryState) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        self._history_lock = True
        self._pause_column_playback()
        if snapshot.map_path:
            scene.load_map_image(snapshot.map_path)
            self.map_status_label.setText(f"当前地图：{Path(snapshot.map_path).name}")
            self.map_view.fit_scene()
        else:
            scene.clear_map()
            self.map_status_label.setText("当前地图：未加载")

        self.operator_order = list(snapshot.operator_order)
        self.operator_labels = dict(snapshot.operator_labels)
        self.keyframe_columns = deepcopy(snapshot.keyframe_columns)
        self.current_keyframe_index = snapshot.current_keyframe_index
        self.current_timeline_row = snapshot.current_timeline_row
        self._transition_duration_ms = snapshot.transition_duration_ms
        self.timeline.duration_slider.setValue(self._transition_duration_ms)

        scene.sync_operator_states(deepcopy(snapshot.scene_states), snapshot.selected_operator_id or None)
        for operator in scene.operator_items():
            self._update_operator_icon(operator)

        self._refresh_property_panel()
        self._history_lock = False
        self._refresh_timeline()

    def _operator_row(self, operator_id: str) -> int:
        try:
            return self.operator_order.index(operator_id)
        except ValueError:
            return -1

    def _current_operator(self) -> OperatorItem | None:
        scene = self._map_scene()
        if scene is None:
            return None
        return scene.selected_operator()

    def _map_scene(self) -> MapScene | None:
        scene = self.map_view.scene()
        if isinstance(scene, MapScene):
            return scene
        return None

    def _update_dirty_state(self) -> None:
        is_dirty = self.is_dirty()
        self.save_project_button.setText("保存工程*" if is_dirty else "保存工程")
        window = self.window()
        if isinstance(window, QWidget):
            title = "R6 Tactics Board"
            if is_dirty:
                title += " *"
            window.setWindowTitle(title)

    def is_dirty(self) -> bool:
        current = self._capture_history_state()
        return self._clean_snapshot is not None and current != self._clean_snapshot

    def confirm_discard_changes(self, action_name: str) -> bool:
        if not self.is_dirty():
            return True

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("未保存的更改")
        dialog.setText(f"当前工程有未保存的更改。是否先保存后再{action_name}？")
        save_button = dialog.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        discard_button = dialog.addButton("不保存", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(save_button)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked is save_button:
            return self._save_project_to_current_path()
        if clicked is discard_button:
            return True
        return clicked is not cancel_button

    @staticmethod
    def _sort_operator_id(operator_id: str) -> int:
        try:
            return int(operator_id)
        except ValueError:
            return 0
