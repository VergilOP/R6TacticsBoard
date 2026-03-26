from copy import deepcopy
from dataclasses import dataclass
from heapq import heappop, heappush
from math import hypot
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget
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

from r6_tactics_board.domain.models import (
    Keyframe,
    MapInteractionPoint,
    MapInfo,
    OperatorDefinition,
    OperatorDisplayMode,
    OperatorFrameState,
    OperatorState,
    OperatorTransitionMode,
    Point2D,
    TacticProject,
    TeamSide,
    Timeline,
    resolve_operator_state,
)
from r6_tactics_board.infrastructure.asset_paths import MAPS_DIR
from r6_tactics_board.infrastructure.debug_logging import debug_log
from r6_tactics_board.infrastructure.asset_registry import AssetRegistry, MapAsset
from r6_tactics_board.infrastructure.project_store import ProjectStore
from r6_tactics_board.presentation.widgets.map_scene import MapScene
from r6_tactics_board.presentation.widgets.map_view import MapView
from r6_tactics_board.presentation.widgets.operator_item import OperatorItem
from r6_tactics_board.presentation.widgets.timeline_widget import TimelineWidget


@dataclass(slots=True)
class EditorHistoryState:
    map_asset_path: str
    map_floor_key: str
    map_image_path: str
    scene_states: list[OperatorState]
    selected_operator_id: str
    operator_order: list[str]
    operator_definitions: dict[str, OperatorDefinition]
    keyframe_columns: list[dict[str, OperatorFrameState]]
    keyframe_names: list[str]
    keyframe_notes: list[str]
    current_keyframe_index: int
    current_timeline_row: int
    transition_duration_ms: int


@dataclass(slots=True)
class PlaybackRouteSegment:
    floor_key: str
    start: Point2D
    end: Point2D
    result_floor_key: str


class PopupAwareComboBox(QComboBox):
    popupHidden = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            """
            QComboBox {
                background-color: rgba(24, 28, 34, 220);
                color: #F3F4F6;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
                padding: 6px 32px 6px 10px;
                min-height: 34px;
            }
            QComboBox:hover {
                border: 1px solid rgba(96, 165, 250, 0.9);
            }
            QComboBox:focus {
                border: 1px solid rgba(96, 165, 250, 1.0);
            }
            QComboBox:disabled {
                color: rgba(243, 244, 246, 0.45);
                background-color: rgba(24, 28, 34, 140);
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(24, 28, 34, 235);
                color: #F3F4F6;
                border: 1px solid rgba(255, 255, 255, 0.08);
                outline: none;
                padding: 4px;
                selection-background-color: rgba(96, 165, 250, 0.28);
                selection-color: #FFFFFF;
            }
            """
        )

    def hidePopup(self) -> None:  # noqa: N802
        super().hidePopup()
        self.popupHidden.emit()


class EditorPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._syncing_panel = False
        self._syncing_keyframe_panel = False
        self._applying_timeline = False
        self._is_playing = False
        self._history_lock = False
        self._rotation_history_snapshot: EditorHistoryState | None = None
        self._operator_transform_history_snapshot: EditorHistoryState | None = None
        self._playback_from_column = -1
        self._playback_to_column = -1
        self._playback_elapsed_ms = 0.0
        self._playback_speed = 1.0
        self._scrubbing_playback_slider = False
        self._hovered_manual_interaction_id = ""
        self._property_panel_refresh_pending = False
        self._transition_duration_ms = 700
        self._playback_start_states: dict[str, OperatorState] = {}
        self._playback_end_states: dict[str, OperatorState] = {}
        self._playback_routes: dict[str, list[PlaybackRouteSegment]] = {}
        self._undo_stack: list[EditorHistoryState] = []
        self._redo_stack: list[EditorHistoryState] = []
        self._history_limit = 100
        self._clean_snapshot: EditorHistoryState | None = None

        self.operator_order: list[str] = []
        self.operator_definitions: dict[str, OperatorDefinition] = {}
        self.keyframe_columns: list[dict[str, OperatorFrameState]] = [{}]
        self.keyframe_names: list[str] = [""]
        self.keyframe_notes: list[str] = [""]
        self.current_keyframe_index = 0
        self.current_timeline_row = -1
        self.current_project_path = ""
        self.current_map_asset_path = ""
        self.current_map_floor_key = ""
        self._current_map_asset: MapAsset | None = None

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
        self.property_hint = BodyLabel("名称、阵营、图标是全局属性；位置、朝向、显示模式、楼层跟随当前时间点。")
        self.selection_label = BodyLabel("当前选中：无")
        self.keyframe_title = SubtitleLabel("关键帧属性")
        self.keyframe_hint = BodyLabel("关键帧名称和备注只作用于当前关键帧列。")
        self.keyframe_name_edit = LineEdit()
        self.keyframe_note_edit = LineEdit()
        self.name_edit = LineEdit()
        self.side_combo = ComboBox()
        self.operator_combo = ComboBox()
        self.rotation_slider = Slider(Qt.Orientation.Horizontal)
        self.rotation_value_label = BodyLabel("0°")
        self.floor_value_label = BodyLabel("-")
        self.display_mode_combo = ComboBox()
        self.transition_mode_combo = ComboBox()
        self.manual_interactions_edit = LineEdit()
        self.manual_interactions_hint = BodyLabel("手动互动点：留空时使用自动路径")
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.floor_panel = QWidget(self)
        self.floor_panel_layout = QVBoxLayout(self.floor_panel)
        self.manual_interaction_combo = PopupAwareComboBox()
        self.manual_interaction_add_button = PushButton("添加")
        self.manual_interaction_remove_button = PushButton("移除最后")
        self.manual_interaction_clear_button = PushButton("清空")
        self.manual_interactions_value_label = BodyLabel("自动路径")
        self.playback_panel = QWidget(self)
        self.playback_panel_layout = QHBoxLayout(self.playback_panel)
        self.playback_previous_button = PushButton("上一项")
        self.playback_play_button = PrimaryPushButton("播放")
        self.playback_pause_button = PushButton("暂停")
        self.playback_next_button = PushButton("下一项")
        self.playback_progress_slider = Slider(Qt.Orientation.Horizontal)
        self.playback_status_label = BodyLabel("未开始")
        self.playback_speed_combo = ComboBox()
        self.playback_duration_label = BodyLabel("过渡 700 ms")
        self.playback_duration_slider = Slider(Qt.Orientation.Horizontal)

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

        self.floor_panel.setObjectName("floor-panel")
        self.floor_panel.hide()
        self.floor_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.floor_panel.setStyleSheet(
            "#floor-panel {"
            "background-color: rgba(24, 28, 34, 215);"
            "border: 1px solid rgba(255, 255, 255, 24);"
            "border-radius: 10px;"
            "}"
        )
        self.floor_panel_layout.setContentsMargins(10, 10, 10, 10)
        self.floor_panel_layout.setSpacing(8)
        self.playback_panel.setObjectName("playback-panel")
        self.playback_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.playback_panel.setStyleSheet(
            "#playback-panel {"
            "background-color: rgba(24, 28, 34, 215);"
            "border: 1px solid rgba(255, 255, 255, 24);"
            "border-radius: 10px;"
            "}"
        )
        self.playback_panel_layout.setContentsMargins(12, 10, 12, 10)
        self.playback_panel_layout.setSpacing(10)
        self.playback_progress_slider.setRange(0, 0)
        self.playback_progress_slider.setSingleStep(1)
        self.playback_progress_slider.setPageStep(1)
        self.playback_progress_slider.setMinimumWidth(260)
        self.playback_duration_slider.setRange(200, 2000)
        self.playback_duration_slider.setSingleStep(100)
        self.playback_duration_slider.setPageStep(100)
        self.playback_duration_slider.setValue(self._transition_duration_ms)
        self.playback_duration_slider.setMaximumWidth(180)
        for index, (label, value) in enumerate((
            ("0.5x", 0.5),
            ("1.0x", 1.0),
            ("1.5x", 1.5),
            ("2.0x", 2.0),
        )):
            self.playback_speed_combo.addItem(label)
            self.playback_speed_combo.setItemData(index, value)
        self.playback_speed_combo.setCurrentIndex(1)
        self.playback_status_label.setFixedWidth(120)
        self.playback_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.playback_panel_layout.addWidget(self.playback_previous_button)
        self.playback_pause_button.hide()
        self.playback_panel_layout.addWidget(self.playback_play_button)
        self.playback_panel_layout.addWidget(self.playback_next_button)
        self.playback_panel_layout.addWidget(self.playback_progress_slider, 1)
        self.playback_panel_layout.addWidget(self.playback_status_label)
        self.playback_panel_layout.addWidget(BodyLabel("速度"))
        self.playback_panel_layout.addWidget(self.playback_speed_combo)
        self.playback_panel_layout.addWidget(self.playback_duration_label)
        self.playback_panel_layout.addWidget(self.playback_duration_slider)

        side_panel = QVBoxLayout()
        side_panel.setSpacing(12)

        property_grid = QGridLayout()
        property_grid.setHorizontalSpacing(12)
        property_grid.setVerticalSpacing(12)
        keyframe_grid = QGridLayout()
        keyframe_grid.setHorizontalSpacing(12)
        keyframe_grid.setVerticalSpacing(12)

        self.name_edit.setPlaceholderText("输入自定义名称")
        self.keyframe_name_edit.setPlaceholderText("例如：开局抢点")
        self.keyframe_note_edit.setPlaceholderText("例如：30 秒内优先控图")
        self.rotation_slider.setRange(0, 359)

        self.side_combo.addItem("进攻")
        self.side_combo.setItemData(0, "attack")
        self.side_combo.addItem("防守")
        self.side_combo.setItemData(1, "defense")

        self.display_mode_combo.addItem("干员图标")
        self.display_mode_combo.setItemData(0, OperatorItem.ICON)
        self.display_mode_combo.addItem("自定义名")
        self.display_mode_combo.setItemData(1, OperatorItem.CUSTOM_NAME)
        self.transition_mode_combo.addItem("自动路径")
        self.transition_mode_combo.setItemData(0, OperatorTransitionMode.AUTO.value)
        self.transition_mode_combo.addItem("手动互动点")
        self.transition_mode_combo.setItemData(1, OperatorTransitionMode.MANUAL.value)
        self.manual_interaction_combo.addItem("当前地图无可用互动点")
        self.manual_interaction_combo.setItemData(0, "")
        self.manual_interactions_edit.setPlaceholderText("例如：interaction-1, interaction-4")

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
        property_grid.addWidget(BodyLabel("楼层"), 6, 0)
        property_grid.addWidget(self.floor_value_label, 6, 1)
        property_grid.addWidget(BodyLabel("路径模式"), 7, 0)
        property_grid.addWidget(self.transition_mode_combo, 7, 1)
        manual_selection_layout = QHBoxLayout()
        manual_selection_layout.setSpacing(8)
        manual_selection_layout.addWidget(self.manual_interaction_combo, 1)
        self.manual_interactions_edit.hide()
        self.manual_interactions_value_label.hide()
        self.manual_interactions_hint.hide()
        property_grid.addLayout(manual_selection_layout, 8, 1)
        property_grid.addWidget(self.manual_interactions_value_label, 10, 1)
        property_grid.addWidget(BodyLabel("手动互动点"), 8, 0)
        property_grid.addWidget(self.manual_interactions_edit, 8, 1)
        property_grid.addWidget(self.manual_interactions_hint, 9, 1)

        keyframe_grid.addWidget(BodyLabel("名称"), 0, 0)
        keyframe_grid.addWidget(self.keyframe_name_edit, 0, 1)
        keyframe_grid.addWidget(BodyLabel("备注"), 1, 0)
        keyframe_grid.addWidget(self.keyframe_note_edit, 1, 1)

        side_panel.addWidget(self.property_title)
        side_panel.addWidget(self.property_hint)
        side_panel.addWidget(self.selection_label)
        side_panel.addLayout(property_grid)
        side_panel.addWidget(self.delete_operator_button)
        side_panel.addSpacing(12)
        side_panel.addWidget(self.keyframe_title)
        side_panel.addWidget(self.keyframe_hint)
        side_panel.addLayout(keyframe_grid)
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
        self.transition_mode_combo.currentIndexChanged.connect(self._update_transition_mode)
        self.keyframe_name_edit.editingFinished.connect(
            lambda: self._update_current_keyframe_name(self.keyframe_name_edit.text())
        )
        self.keyframe_note_edit.editingFinished.connect(
            lambda: self._update_current_keyframe_note(self.keyframe_note_edit.text())
        )

        self.timeline.add_keyframe_requested.connect(self._add_keyframe_column)
        self.timeline.insert_keyframe_requested.connect(self._insert_keyframe_column)
        self.timeline.duplicate_keyframe_requested.connect(self._duplicate_keyframe_column)
        self.timeline.delete_keyframe_requested.connect(self._delete_current_keyframe_column)
        self.timeline.capture_requested.connect(self._capture_selected_operator_to_current_cell)
        self.timeline.capture_column_requested.connect(self._capture_all_operators_to_current_column)
        self.timeline.clear_cell_requested.connect(self._clear_current_cell)
        self.timeline.cell_selected.connect(self._select_timeline_cell)
        self.timeline.keyframe_column_moved.connect(self._move_keyframe_column)
        self.timeline.operator_row_moved.connect(self._move_operator_row)
        self.playback_timer.timeout.connect(self._advance_playback)
        self.map_view.viewport_resized.connect(self._position_overlay_panels)
        self.playback_previous_button.clicked.connect(self._go_to_previous_column)
        self.playback_next_button.clicked.connect(self._go_to_next_column)
        self.playback_play_button.clicked.connect(self._toggle_column_playback)
        self.playback_duration_slider.valueChanged.connect(self._set_transition_duration)
        self.playback_speed_combo.currentIndexChanged.connect(self._update_playback_speed)
        self.manual_interaction_combo.activated.connect(self._select_manual_interaction_candidate)
        self.manual_interaction_combo.highlighted.connect(self._preview_manual_interaction_hover)
        self.manual_interaction_combo.popupHidden.connect(self._on_manual_interaction_popup_hidden)
        self.playback_progress_slider.sliderPressed.connect(self._on_playback_slider_pressed)
        self.playback_progress_slider.sliderMoved.connect(self._on_playback_slider_moved)
        self.playback_progress_slider.sliderReleased.connect(self._on_playback_slider_released)

        scene = self._map_scene()
        if scene is not None:
            scene.selectionChanged.connect(self._on_scene_selection_changed)
            scene.operator_transform_started.connect(self._on_operator_transform_started)
            scene.operator_move_finished.connect(self._on_operator_move_finished)

    def _load_map(self) -> None:
        if not self.confirm_discard_changes("加载地图"):
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择地图",
            str(MAPS_DIR),
            "Map Metadata (*.json)",
        )
        if file_path:
            self._load_map_asset_with_history(file_path)

    def _load_map_file(self, file_path: str) -> None:
        scene = self._map_scene()
        if scene is None:
            return
        before = self._capture_history_state()
        if scene.load_map_image(file_path):
            self._pause_column_playback()
            self.map_status_label.setText(f"当前地图：{Path(file_path).name}")
            self.map_view.fit_scene()
            self.current_map_asset_path = ""
            self.current_map_floor_key = ""
            self._current_map_asset = None
            self._rebuild_floor_panel()
            self._refresh_property_panel()
            self._commit_history(before)

    def load_map_from_path(self, file_path: str) -> None:
        self._load_map_asset_with_history(file_path)

    def _load_map_asset_with_history(self, map_asset_path: str) -> bool:
        before = self._capture_history_state()
        preferred_floor_key = self.current_map_floor_key
        self._pause_column_playback()
        self.operator_order = []
        self.operator_definitions = {}
        self.keyframe_columns = [{}]
        self.keyframe_names = [""]
        self.keyframe_notes = [""]
        self.current_keyframe_index = 0
        self.current_timeline_row = -1
        if not self._load_map_asset(map_asset_path, floor_key=preferred_floor_key):
            self._restore_history_state(before)
            return False
        self._apply_timeline_column(self.current_keyframe_index)
        self._commit_history(before)
        return True

    def _load_map_asset(
        self,
        map_asset_path: str,
        floor_key: str = "",
        fit_view: bool = True,
        pause_playback: bool = True,
    ) -> bool:
        scene = self._map_scene()
        if scene is None:
            return False

        asset = self.asset_registry.load_map_asset(map_asset_path)
        if asset is None or not asset.floors:
            return False

        selected_floor = next(
            (floor for floor in asset.floors if floor.key == floor_key),
            asset.floors[0],
        )
        if not scene.load_map_image(selected_floor.image_path):
            return False

        if pause_playback:
            self._pause_column_playback()
        self.current_map_asset_path = asset.path
        self.current_map_floor_key = selected_floor.key
        self._current_map_asset = asset
        self.map_status_label.setText(f"当前地图：{asset.name} / {selected_floor.name}")
        self._rebuild_floor_panel()
        if fit_view:
            self.map_view.fit_scene()
        self._refresh_property_panel()
        return True

    def _switch_map_floor(self, floor_key: str) -> None:
        if not self.current_map_asset_path or floor_key == self.current_map_floor_key:
            return
        before = self._capture_history_state()
        if self._load_map_asset(self.current_map_asset_path, floor_key=floor_key, fit_view=False):
            self._apply_timeline_column(self.current_keyframe_index)
            self._commit_history(before)

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
        operator.set_floor_key(self._current_floor_key())
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
        operator.set_floor_key(self._current_floor_key())
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
        if operator is None:
            return
        self._delete_operator_by_id(operator.operator_id, confirm=True)

    def _refresh_property_panel(self) -> None:
        if self.manual_interaction_combo.view().isVisible():
            debug_log("editor: property panel refresh deferred because manual interaction popup is visible")
            self._schedule_property_panel_refresh()
            return
        operator = self._current_operator()
        target_operator_id = self._target_operator_id()
        debug_log(
            f"editor: refresh property panel target={target_operator_id or '-'} column={self.current_keyframe_index} row={self.current_timeline_row}"
        )
        target_definition = (
            self.operator_definitions.get(target_operator_id)
            if target_operator_id is not None
            else None
        )
        target_frame = (
            self._resolved_frame_state(target_operator_id, self.current_keyframe_index)
            if target_operator_id is not None and 0 <= self.current_keyframe_index < len(self.keyframe_columns)
            else None
        )

        self._syncing_panel = True
        if operator is None and target_operator_id is None:
            self.selection_label.setText("当前选中：无")
            self.name_edit.setText("")
            self.side_combo.setCurrentIndex(0)
            self._refresh_operator_combo("attack")
            self.rotation_slider.setValue(0)
            self.rotation_value_label.setText("0°")
            self.floor_value_label.setText(self._current_floor_key())
            self.display_mode_combo.setCurrentIndex(0)
            self._set_combo_value(self.transition_mode_combo, OperatorTransitionMode.AUTO.value)
            self._refresh_manual_interaction_controls([])
            self._set_property_enabled(False)
        else:
            operator_id = operator.operator_id if operator is not None else target_operator_id
            custom_name = operator.custom_name if operator is not None else (
                target_definition.custom_name if target_definition is not None else f"干员 {operator_id}"
            )
            side = operator.side if operator is not None else (
                target_definition.side.value if target_definition is not None else "attack"
            )
            operator_key = operator.operator_key if operator is not None else (
                target_definition.operator_key if target_definition is not None else ""
            )
            rotation = int(operator.rotation()) % 360 if operator is not None else (
                int(target_frame.rotation) % 360 if target_frame is not None else 0
            )
            floor_key = operator.floor_key if operator is not None else (
                target_frame.floor_key if target_frame is not None and target_frame.floor_key else self._current_floor_key()
            )
            display_mode = operator.display_mode if operator is not None else (
                OperatorItem.ICON
                if target_frame is None or target_frame.display_mode == OperatorDisplayMode.ICON
                else OperatorItem.CUSTOM_NAME
            )
            transition_mode = (
                target_frame.transition_mode.value
                if target_frame is not None
                else OperatorTransitionMode.AUTO.value
            )
            manual_interaction_ids = list(target_frame.manual_interaction_ids) if target_frame is not None else []
            if self._is_transition_mode_locked(target_operator_id):
                transition_mode = OperatorTransitionMode.AUTO.value
                manual_interaction_ids = []

            if operator is not None:
                self.selection_label.setText(f"当前选中：干员 {operator_id}")
            else:
                self.selection_label.setText(f"当前目标：干员 {operator_id}（时间轴）")

            self.name_edit.setText(custom_name)
            self.side_combo.setCurrentIndex(0 if side == "attack" else 1)
            self._refresh_operator_combo(side, operator_key)
            self.rotation_slider.setValue(rotation)
            self.rotation_value_label.setText(f"{rotation}°")
            self.floor_value_label.setText(floor_key or self._current_floor_key())
            self.display_mode_combo.setCurrentIndex(
                0 if display_mode == OperatorItem.ICON else 1
            )
            self._set_combo_value(self.transition_mode_combo, transition_mode)
            self._refresh_manual_interaction_controls(manual_interaction_ids)
            self._set_property_enabled(True)
        self._syncing_panel = False

        self._syncing_keyframe_panel = True
        self.keyframe_name_edit.setText(self._current_keyframe_name())
        self.keyframe_note_edit.setText(self._current_keyframe_note())
        has_keyframe = 0 <= self.current_keyframe_index < len(self.keyframe_columns)
        self.keyframe_name_edit.setEnabled(has_keyframe)
        self.keyframe_note_edit.setEnabled(has_keyframe)
        self._syncing_keyframe_panel = False
        debug_log("editor: refresh property panel done")

    def _rebuild_floor_panel(self) -> None:
        while self.floor_panel_layout.count():
            item = self.floor_panel_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        asset = self._current_map_asset
        if asset is None or len(asset.floors) <= 1:
            self.floor_panel.hide()
            return

        self.floor_panel_layout.addWidget(BodyLabel("楼层"))
        for floor in asset.floors:
            button = PrimaryPushButton(floor.name) if floor.key == self.current_map_floor_key else PushButton(floor.name)
            button.clicked.connect(lambda checked=False, key=floor.key: self._switch_map_floor(key))
            self.floor_panel_layout.addWidget(button)

        self.floor_panel.show()
        self._position_floor_panel()
        self.floor_panel.raise_()
        self.floor_panel.update()
        QTimer.singleShot(0, self._position_floor_panel)

    def _position_floor_panel(self) -> None:
        if self.floor_panel.isHidden():
            return
        self.floor_panel_layout.activate()
        self.floor_panel.setFixedSize(self.floor_panel_layout.sizeHint())
        map_rect = self.map_view.geometry()
        x = map_rect.left() + 12
        y = max(map_rect.top() + 12, map_rect.top() + (map_rect.height() - self.floor_panel.height()) // 2)
        self.floor_panel.move(x, y)
        self.floor_panel.raise_()

    def _position_playback_panel(self) -> None:
        self.playback_panel_layout.activate()
        self.playback_panel.setFixedSize(self.playback_panel_layout.sizeHint())
        map_rect = self.map_view.geometry()
        x = map_rect.left() + max((map_rect.width() - self.playback_panel.width()) // 2, 12)
        y = map_rect.bottom() - self.playback_panel.height() - 12
        self.playback_panel.move(x, y)
        self.playback_panel.raise_()

    def _position_overlay_panels(self) -> None:
        self._position_floor_panel()
        self._position_playback_panel()

    def _set_property_enabled(self, enabled: bool) -> None:
        self.name_edit.setEnabled(enabled)
        self.side_combo.setEnabled(enabled)
        self.operator_combo.setEnabled(enabled)
        self.rotation_slider.setEnabled(enabled)
        self.display_mode_combo.setEnabled(enabled)
        transition_editable = enabled and not self._is_transition_mode_locked(self._target_operator_id())
        self.transition_mode_combo.setEnabled(transition_editable)
        manual_enabled = (
            enabled
            and transition_editable
            and self.transition_mode_combo.currentData() == OperatorTransitionMode.MANUAL.value
        )
        self.manual_interaction_combo.setEnabled(manual_enabled)
        self.manual_interaction_add_button.hide()
        self.manual_interaction_remove_button.hide()
        self.manual_interaction_clear_button.hide()
        self.delete_operator_button.setEnabled(enabled)

    def _manual_interactions_hint_text(self) -> str:
        if self._current_map_asset is None or not self._current_map_asset.interactions:
            return "当前地图没有可用互动点，手动路径将回退为自动。"
        interaction_ids = ", ".join(item.id for item in self._current_map_asset.interactions[:6])
        if len(self._current_map_asset.interactions) > 6:
            interaction_ids += " ..."
        return f"可用互动点 ID：{interaction_ids}"

    def _refresh_manual_interaction_controls(self, selected_ids: list[str]) -> None:
        operator_id = self._target_operator_id()
        interactions = self._available_manual_interactions(operator_id, selected_ids)
        transition_locked = self._is_transition_mode_locked(operator_id)
        self.manual_interaction_combo.blockSignals(True)
        self.manual_interaction_combo.clear()
        if interactions and not transition_locked:
            for index, interaction in enumerate(interactions):
                self.manual_interaction_combo.addItem(self._interaction_choice_label(interaction))
                self.manual_interaction_combo.setItemData(index, interaction.id)
            if selected_ids:
                last_id = selected_ids[-1]
                for index in range(self.manual_interaction_combo.count()):
                    if self.manual_interaction_combo.itemData(index) == last_id:
                        self.manual_interaction_combo.setCurrentIndex(index)
                        break
        else:
            self.manual_interaction_combo.addItem("当前步骤无可选互动点")
            self.manual_interaction_combo.setItemData(0, "")
        self.manual_interaction_combo.blockSignals(False)
        if not interactions:
            self._hovered_manual_interaction_id = ""
        self.manual_interactions_value_label.setText(self._manual_interaction_summary(selected_ids))
        if transition_locked:
            self.manual_interactions_hint.setText("当前关键帧与下一关键帧在同一楼层，路径模式固定为自动。")
        elif not self._has_next_transition_target(operator_id):
            self.manual_interactions_hint.setText("当前关键帧没有下一步目标，暂不需要手动互动点。")
        elif not interactions:
            self.manual_interactions_hint.setText("当前楼层没有可用互动点可通往下一关键帧楼层。")
        else:
            labels = ", ".join(self._interaction_choice_label(item) for item in interactions[:3])
            if len(interactions) > 3:
                labels += " ..."
            self.manual_interactions_hint.setText(f"当前可选互动点：{labels}")
        self._sync_scene_interaction_overlays(selected_ids)

    def _available_manual_interactions(
        self,
        operator_id: str | None,
        selected_ids: list[str] | None = None,
    ) -> list[MapInteractionPoint]:
        if self._current_map_asset is None or operator_id is None:
            return []
        start_state, end_state = self._current_transition_states(operator_id)
        if start_state is None or end_state is None:
            return []
        start_floor = start_state.floor_key or self._current_floor_key()
        end_floor = end_state.floor_key or start_floor
        candidates: list[tuple[MapInteractionPoint, str]] = []
        for item in self._current_map_asset.interactions:
            target_floor = self._resolve_manual_target_floor(item, start_floor)
            if target_floor is None:
                continue
            if not self._can_reach_floor(target_floor, end_floor):
                continue
            candidates.append((item, target_floor))

        return sorted(
            [item for item, _ in candidates],
            key=lambda item: (item.floor_key, item.id),
        )

    def _manual_interaction_prefix(
        self,
        start_floor: str,
        manual_interaction_ids: list[str],
    ) -> tuple[list[tuple[MapInteractionPoint, str]], str] | None:
        if self._current_map_asset is None:
            return None

        interactions_by_id = {
            interaction.id: interaction
            for interaction in self._current_map_asset.interactions
        }
        route: list[tuple[MapInteractionPoint, str]] = []
        current_floor = start_floor

        for interaction_id in manual_interaction_ids:
            interaction = interactions_by_id.get(interaction_id)
            if interaction is None:
                return None
            target_floor = self._resolve_manual_target_floor(interaction, current_floor)
            if target_floor is None:
                return None
            route.append((interaction, target_floor))
            current_floor = target_floor

        return route, current_floor

    def _current_transition_states(
        self,
        operator_id: str | None,
    ) -> tuple[OperatorState | None, OperatorState | None]:
        if operator_id is None:
            return (None, None)
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return (None, None)
        next_column = self.current_keyframe_index + 1
        if next_column >= len(self.keyframe_columns):
            return (None, None)
        return (
            self._resolved_state(operator_id, self.current_keyframe_index),
            self._resolved_state(operator_id, next_column),
        )

    def _has_next_transition_target(self, operator_id: str | None) -> bool:
        start_state, end_state = self._current_transition_states(operator_id)
        return start_state is not None and end_state is not None

    def _is_transition_mode_locked(self, operator_id: str | None) -> bool:
        start_state, end_state = self._current_transition_states(operator_id)
        if start_state is None or end_state is None:
            return True
        start_floor = start_state.floor_key or self._current_floor_key()
        end_floor = end_state.floor_key or start_floor
        return start_floor == end_floor

    def _can_reach_floor(self, start_floor: str | None, end_floor: str) -> bool:
        if not start_floor:
            return False
        if start_floor == end_floor:
            return True
        seen = {start_floor}
        queue = [start_floor]
        while queue:
            current_floor = queue.pop(0)
            for _, target_floor in self._iter_interaction_transitions(current_floor):
                if target_floor == end_floor:
                    return True
                if target_floor not in seen:
                    seen.add(target_floor)
                    queue.append(target_floor)
        return False

    @staticmethod
    def _interaction_choice_label(interaction: MapInteractionPoint) -> str:
        suffix = f" | {interaction.label}" if interaction.label else ""
        return f"{interaction.floor_key} | {interaction.id}{suffix}"

    def _manual_interaction_summary(self, selected_ids: list[str]) -> str:
        if not selected_ids:
            return "自动路径"
        lookup = {
            item.id: self._interaction_choice_label(item)
            for item in (self._current_map_asset.interactions if self._current_map_asset is not None else [])
        }
        parts = [
            f"{index + 1}. {lookup.get(interaction_id, interaction_id)}"
            for index, interaction_id in enumerate(selected_ids)
        ]
        return "  ->  ".join(parts)

    def _sync_scene_interaction_overlays(self, selected_ids: list[str] | None = None) -> None:
        scene = self._map_scene()
        if scene is None:
            return
        target_operator_id = self._target_operator_id()
        target_frame = (
            self._resolved_frame_state(target_operator_id, self.current_keyframe_index)
            if target_operator_id is not None and 0 <= self.current_keyframe_index < len(self.keyframe_columns)
            else None
        )
        transition_locked = self._is_transition_mode_locked(target_operator_id)
        highlighted_ids = selected_ids
        if highlighted_ids is None and target_frame is not None:
            highlighted_ids = list(target_frame.manual_interaction_ids)
        candidate_interactions = self._available_manual_interactions(target_operator_id, highlighted_ids or [])
        highlighted_lookup = set(highlighted_ids or [])
        overlay_interactions = [
            interaction
            for interaction in (self._current_map_asset.interactions if self._current_map_asset is not None else [])
            if interaction.id in highlighted_lookup
            or interaction in candidate_interactions
        ]
        visible = bool(
            self._current_map_asset is not None
            and target_operator_id is not None
            and not transition_locked
            and self.transition_mode_combo.currentData() == OperatorTransitionMode.MANUAL.value
        )
        scene.set_interaction_overlays(
            overlay_interactions,
            self._current_floor_key(),
            visible,
            highlighted_ids or [],
            hovered_id=self._hovered_manual_interaction_id,
        )

    def _clear_manual_interaction_hover(self) -> None:
        if not self._hovered_manual_interaction_id:
            return
        self._hovered_manual_interaction_id = ""
        self._sync_scene_interaction_overlays()

    def _on_manual_interaction_popup_hidden(self) -> None:
        QTimer.singleShot(0, self._clear_manual_interaction_hover)

    def _schedule_property_panel_refresh(self) -> None:
        if self._property_panel_refresh_pending:
            return
        self._property_panel_refresh_pending = True

        def run() -> None:
            self._property_panel_refresh_pending = False
            debug_log("editor: deferred property panel refresh")
            self._refresh_property_panel()

        QTimer.singleShot(0, run)

    @staticmethod
    def _set_combo_value(combo: ComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    def _current_transition_frame(self, operator_id: str) -> OperatorFrameState | None:
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return None
        frame = self.keyframe_columns[self.current_keyframe_index].get(operator_id)
        if frame is not None:
            return deepcopy(frame)
        frame = self._resolved_frame_state(operator_id, self.current_keyframe_index)
        return deepcopy(frame) if frame is not None else None

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_overlay_panels()

    def _apply_name_edit(self) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        operator_id = operator.operator_id if operator is not None else self._target_operator_id()
        current_name = operator.custom_name if operator is not None else (
            self.operator_definitions.get(operator_id).custom_name
            if operator_id is not None and operator_id in self.operator_definitions
            else ""
        )
        if operator_id is None:
            return
        name = self.name_edit.text().strip() or f"干员 {operator_id}"
        if name == current_name:
            return
        before = self._capture_history_state()
        self._apply_global_operator_metadata(operator_id, custom_name=name)
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _update_selected_side(self, index: int) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        operator_id = operator.operator_id if operator is not None else self._target_operator_id()
        current_side = operator.side if operator is not None else (
            self.operator_definitions.get(operator_id).side.value
            if operator_id is not None and operator_id in self.operator_definitions
            else "attack"
        )
        if operator_id is None:
            return

        side = self.side_combo.itemData(index)
        if side is None or side == current_side:
            return

        before = self._capture_history_state()
        self._apply_global_operator_metadata(operator_id, side=side)
        self._refresh_operator_combo(side)
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _update_selected_operator_asset(self, index: int) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        operator_id = operator.operator_id if operator is not None else self._target_operator_id()
        current_key = operator.operator_key if operator is not None else (
            self.operator_definitions.get(operator_id).operator_key
            if operator_id is not None and operator_id in self.operator_definitions
            else ""
        )
        if operator_id is None:
            return

        operator_key = self.operator_combo.itemData(index) or ""
        if operator_key == current_key:
            return
        before = self._capture_history_state()
        self._apply_global_operator_metadata(operator_id, operator_key=operator_key)
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _on_rotation_slider_pressed(self) -> None:
        if self._syncing_panel:
            return
        if self._current_operator() is not None or self._target_operator_id() is not None:
            self._rotation_history_snapshot = self._capture_history_state()

    def _update_selected_rotation(self, value: int) -> None:
        self.rotation_value_label.setText(f"{value}°")
        if self._syncing_panel:
            return
        operator = self._current_operator()
        if operator is None:
            operator_id = self._target_operator_id()
            if operator_id is None or not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
                return
            frame = self.keyframe_columns[self.current_keyframe_index].get(operator_id)
            if frame is None:
                frame = self._resolved_frame_state(operator_id, self.current_keyframe_index)
                if frame is None:
                    frame = OperatorFrameState(
                        id=operator_id,
                        position=Point2D(x=0, y=0),
                        rotation=value,
                        display_mode=OperatorDisplayMode.ICON,
                        floor_key=self._current_floor_key(),
                    )
                else:
                    frame = deepcopy(frame)
            frame.rotation = value
            frame.floor_key = self._current_floor_key()
            self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
            self._refresh_property_panel()
            self._refresh_timeline()
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
        mode = self.display_mode_combo.itemData(index)
        if mode is None:
            return
        if operator is None:
            operator_id = self._target_operator_id()
            if operator_id is None or not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
                return
            current_frame = self.keyframe_columns[self.current_keyframe_index].get(operator_id)
            if current_frame is None:
                current_frame = self._resolved_frame_state(operator_id, self.current_keyframe_index)
                if current_frame is None:
                    current_frame = OperatorFrameState(
                        id=operator_id,
                        position=Point2D(x=0, y=0),
                        rotation=0,
                        display_mode=OperatorDisplayMode(mode),
                        floor_key=self._current_floor_key(),
                    )
                else:
                    current_frame = deepcopy(current_frame)
            if current_frame.display_mode.value == mode:
                return
            before = self._capture_history_state()
            current_frame.display_mode = OperatorDisplayMode(mode)
            current_frame.floor_key = self._current_floor_key()
            self.keyframe_columns[self.current_keyframe_index][operator_id] = current_frame
            self._refresh_property_panel()
            self._refresh_timeline()
            self._commit_history(before)
            return

        if mode != operator.display_mode:
            before = self._capture_history_state()
            operator.set_display_mode(mode)
            self._capture_selected_operator_to_current_cell(refresh_history=False)
            self._commit_history(before)

    def _update_transition_mode(self, index: int) -> None:
        if self._syncing_panel:
            return
        operator_id = self._target_operator_id()
        if operator_id is None or not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        mode = self.transition_mode_combo.itemData(index)
        if mode is None:
            return

        frame = self._current_transition_frame(operator_id)
        if frame is None:
            frame = OperatorFrameState(
                id=operator_id,
                position=Point2D(x=0, y=0),
                rotation=0,
                display_mode=OperatorDisplayMode.ICON,
                floor_key=self._current_floor_key(),
            )
        if frame.transition_mode.value == mode:
            return

        before = self._capture_history_state()
        frame.transition_mode = OperatorTransitionMode(mode)
        if frame.transition_mode == OperatorTransitionMode.AUTO:
            frame.manual_interaction_ids = []
        self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _set_manual_interaction_ids(self, operator_id: str, manual_ids: list[str]) -> None:
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return

        available_ids = {
            item.id
            for item in (self._current_map_asset.interactions if self._current_map_asset is not None else [])
        }
        normalized_ids = [item for item in manual_ids if item in available_ids]
        frame = self._current_transition_frame(operator_id)
        if frame is None:
            frame = OperatorFrameState(
                id=operator_id,
                position=Point2D(x=0, y=0),
                rotation=0,
                display_mode=OperatorDisplayMode.ICON,
                floor_key=self._current_floor_key(),
            )

        normalized_mode = OperatorTransitionMode.MANUAL if normalized_ids else OperatorTransitionMode.AUTO
        if frame.manual_interaction_ids == normalized_ids and frame.transition_mode == normalized_mode:
            return

        debug_log(
            f"editor: set manual interactions operator={operator_id} column={self.current_keyframe_index} ids={normalized_ids}"
        )
        before = self._capture_history_state()
        frame.manual_interaction_ids = normalized_ids
        frame.transition_mode = normalized_mode
        self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
        self._refresh_timeline()
        self._commit_history(before)
        self._schedule_property_panel_refresh()

    def _select_manual_interaction_candidate(self, index: int) -> None:
        if index < 0 or index >= self.manual_interaction_combo.count():
            return
        interaction_id = self.manual_interaction_combo.itemData(index)
        if not interaction_id:
            return
        debug_log(f"editor: select manual interaction candidate index={index} id={interaction_id}")
        QTimer.singleShot(0, lambda value=str(interaction_id): self._apply_manual_interaction_candidate(value))

    def _apply_manual_interaction_candidate(self, interaction_id: str) -> None:
        if self._syncing_panel:
            return
        operator_id = self._target_operator_id()
        if operator_id is None:
            return
        if self._is_transition_mode_locked(operator_id):
            return
        frame = self._current_transition_frame(operator_id)
        current_ids = list(frame.manual_interaction_ids) if frame is not None else []
        next_ids = [interaction_id]
        if current_ids == next_ids:
            return
        debug_log(
            f"editor: apply manual interaction operator={operator_id} column={self.current_keyframe_index} id={interaction_id}"
        )
        self._set_manual_interaction_ids(operator_id, next_ids)
        self._hovered_manual_interaction_id = ""

    def _preview_manual_interaction_hover(self, index: int) -> None:
        if self._syncing_panel:
            return
        if index < 0 or index >= self.manual_interaction_combo.count():
            return
        interaction_id = self.manual_interaction_combo.itemData(index)
        self._hovered_manual_interaction_id = str(interaction_id or "")
        self._sync_scene_interaction_overlays()

    def _apply_manual_interactions_edit(self) -> None:
        if self._syncing_panel:
            return
        operator_id = self._target_operator_id()
        if operator_id is None or not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return

        raw_ids = [
            item.strip()
            for item in self.manual_interactions_edit.text().split(",")
            if item.strip()
        ]
        available_ids = {
            interaction.id
            for interaction in (self._current_map_asset.interactions if self._current_map_asset is not None else [])
        }
        manual_ids = [item for item in raw_ids if item in available_ids]

        frame = self._current_transition_frame(operator_id)
        if frame is None:
            frame = OperatorFrameState(
                id=operator_id,
                position=Point2D(x=0, y=0),
                rotation=0,
                display_mode=OperatorDisplayMode.ICON,
                floor_key=self._current_floor_key(),
            )

        normalized_mode = (
            OperatorTransitionMode.MANUAL
            if manual_ids
            else OperatorTransitionMode.AUTO
        )
        if frame.manual_interaction_ids == manual_ids and frame.transition_mode == normalized_mode:
            return

        before = self._capture_history_state()
        frame.manual_interaction_ids = manual_ids
        frame.transition_mode = normalized_mode
        self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _add_keyframe_column(self) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        self.keyframe_columns.append({})
        self.keyframe_names.append("")
        self.keyframe_notes.append("")
        self.current_keyframe_index = len(self.keyframe_columns) - 1
        self._refresh_timeline()
        self._commit_history(before)

    def _insert_keyframe_column(self) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        insert_index = min(self.current_keyframe_index + 1, len(self.keyframe_columns))
        self.keyframe_columns.insert(insert_index, {})
        self.keyframe_names.insert(insert_index, "")
        self.keyframe_notes.insert(insert_index, "")
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
        source_name = self.keyframe_names[self.current_keyframe_index]
        self.keyframe_names.insert(insert_index, f"{source_name} 副本" if source_name else "")
        self.keyframe_notes.insert(insert_index, self.keyframe_notes[self.current_keyframe_index])
        self.current_keyframe_index = insert_index
        self._refresh_timeline()
        self._commit_history(before)

    def _delete_current_keyframe_column(self) -> None:
        self._delete_keyframe_column_at(self.current_keyframe_index)

    def _delete_keyframe_column_at(self, column_index: int) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        if not self.keyframe_columns or not (0 <= column_index < len(self.keyframe_columns)):
            return
        if len(self.keyframe_columns) == 1:
            self.keyframe_columns = [{}]
            self.keyframe_names = [""]
            self.keyframe_notes = [""]
            self.current_keyframe_index = 0
            self.current_timeline_row = -1
            self._apply_timeline_column(0)
            self._refresh_timeline()
            self._commit_history(before)
            return

        keyframe_label = self._keyframe_label(column_index)
        dialog = MessageBox(
            "删除当前列",
            f"确定删除关键帧列“{keyframe_label}”吗？该列显式记录的内容将被移除。",
            self,
        )
        dialog.yesButton.setText("确定")
        dialog.cancelButton.setText("取消")
        if not dialog.exec():
            return

        del self.keyframe_columns[column_index]
        del self.keyframe_names[column_index]
        del self.keyframe_notes[column_index]
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
        state = self._frame_state_from_operator(operator)
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
        for operator in scene.operator_items():
            state = self._frame_state_from_operator(operator)
            if state is not None:
                self.keyframe_columns[self.current_keyframe_index][operator.operator_id] = state
        self._refresh_timeline()
        self._commit_history(before)

    def _clear_current_cell(self) -> None:
        self._delete_timeline_cell_at(self.current_timeline_row, self.current_keyframe_index)

    def _delete_timeline_cell_at(self, row: int, column: int) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        if not (0 <= column < len(self.keyframe_columns)):
            return
        if not (0 <= row < len(self.operator_order)):
            return
        operator_id = self.operator_order[row]
        self.keyframe_columns[column].pop(operator_id, None)
        self.current_timeline_row = row
        self.current_keyframe_index = column
        self._refresh_timeline()
        self._apply_timeline_column(column)
        self._commit_history(before)

    def _select_timeline_cell(self, row: int, column: int) -> None:
        self.current_timeline_row = row
        if column >= 0:
            self.current_keyframe_index = column
        self._pause_column_playback()
        if self.current_keyframe_index >= 0:
            self._apply_column_with_focus_floor(self.current_keyframe_index)

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
            if state is not None and self._state_matches_current_floor(state):
                resolved_states.append(deepcopy(state))

        scene.sync_operator_states(resolved_states)
        for operator in scene.operator_items():
            self._update_operator_icon(operator)

        self._sync_operator_registry()
        self._refresh_property_panel()
        self._applying_timeline = False
        self._refresh_timeline()

    def _resolved_frame_state(self, operator_id: str, column: int) -> OperatorFrameState | None:
        for current in range(column, -1, -1):
            state = self.keyframe_columns[current].get(operator_id)
            if state is not None:
                return state
        return None

    def _resolved_state(self, operator_id: str, column: int) -> OperatorState | None:
        definition = self.operator_definitions.get(operator_id)
        frame = self._resolved_frame_state(operator_id, column)
        if definition is None or frame is None:
            return None
        return resolve_operator_state(definition, frame)

    def _resolved_state_map(self, column: int) -> dict[str, OperatorState]:
        result: dict[str, OperatorState] = {}
        for operator_id in self.operator_order:
            state = self._resolved_state(operator_id, column)
            if state is not None:
                result[operator_id] = deepcopy(state)
        return result

    def _refresh_timeline(self) -> None:
        operator_labels = [
            f"{operator_id} | {self._operator_label(operator_id)}"
            for operator_id in self.operator_order
        ]
        keyframe_labels = [self._keyframe_label(index) for index in range(len(self.keyframe_columns))]
        explicit_cells = {
            (row, column)
            for column, frame in enumerate(self.keyframe_columns)
            for row, operator_id in enumerate(self.operator_order)
            if operator_id in frame
        }
        self.timeline.set_grid(
            operator_labels,
            keyframe_labels,
            list(self.keyframe_notes),
            explicit_cells,
            self.current_timeline_row,
            self.current_keyframe_index,
            self._is_playing,
        )
        self._refresh_playback_panel()
        self._sync_scene_placement_target()
        self._sync_scene_preview_paths()
        self._sync_scene_interaction_overlays()
        self.undo_button.setEnabled(bool(self._undo_stack))
        self.redo_button.setEnabled(bool(self._redo_stack))
        self._update_dirty_state()

    def _refresh_playback_panel(self) -> None:
        max_steps = max(len(self.keyframe_columns) - 1, 0)
        self.playback_progress_slider.blockSignals(True)
        self.playback_progress_slider.setRange(0, max_steps * 1000)
        if self._scrubbing_playback_slider:
            progress_value = self.playback_progress_slider.value()
        elif self._is_playing and self._playback_from_column >= 0 and self._playback_to_column >= 0:
            segment_progress = min(self._playback_elapsed_ms / max(self._transition_duration_ms, 1), 1.0)
            progress_value = int((self._playback_from_column + segment_progress) * 1000)
        else:
            progress_value = max(self.current_keyframe_index, 0) * 1000
        self.playback_progress_slider.setValue(progress_value)
        self.playback_progress_slider.blockSignals(False)

        current_label = self._keyframe_label(self.current_keyframe_index) if self.keyframe_columns else "-"
        if self._is_playing and self._playback_to_column >= 0:
            target_label = self._keyframe_label(self._playback_to_column)
            self.playback_status_label.setText(f"{current_label} -> {target_label}")
        else:
            self.playback_status_label.setText(current_label)

        has_columns = bool(self.keyframe_columns)
        self.playback_previous_button.setEnabled(has_columns and self.current_keyframe_index > 0 and not self._is_playing)
        self.playback_next_button.setEnabled(
            has_columns
            and self.current_keyframe_index < len(self.keyframe_columns) - 1
            and not self._is_playing
        )
        self.playback_play_button.setEnabled(len(self.keyframe_columns) > 1)
        self.playback_play_button.setText("暂停" if self._is_playing else "播放")
        self.playback_duration_label.setText(f"过渡 {self._transition_duration_ms} ms")
        self._position_playback_panel()

    def _update_playback_speed(self, index: int) -> None:
        value = self.playback_speed_combo.itemData(index)
        self._playback_speed = float(value) if value is not None else 1.0

    def _toggle_column_playback(self) -> None:
        if self._is_playing:
            self._pause_column_playback()
        else:
            self._start_column_playback()

    def _on_playback_slider_pressed(self) -> None:
        if self._is_playing:
            self._pause_column_playback()
        self._scrubbing_playback_slider = True

    def _on_playback_slider_moved(self, value: int) -> None:
        if not self.keyframe_columns:
            return
        target_column = self._playback_slider_target_column(value)
        if target_column == self.current_keyframe_index:
            self._refresh_playback_panel()
            return
        self.current_keyframe_index = target_column
        self._apply_column_with_focus_floor(self.current_keyframe_index)

    def _on_playback_slider_released(self) -> None:
        self._scrubbing_playback_slider = False
        if not self.keyframe_columns:
            return
        target_column = self._playback_slider_target_column(self.playback_progress_slider.value())
        if target_column != self.current_keyframe_index:
            self.current_keyframe_index = target_column
            self._apply_column_with_focus_floor(self.current_keyframe_index)
        else:
            self._refresh_timeline()

    def _playback_slider_target_column(self, value: int) -> int:
        target_column = round(value / 1000)
        return max(0, min(target_column, len(self.keyframe_columns) - 1))

    def _on_scene_selection_changed(self) -> None:
        scene = self._map_scene()
        operator = self._current_operator()
        if operator is None and scene is not None and scene.selectedItems():
            return
        # Keep the timeline cell as the source of truth for placement mode.
        # Scene selection can temporarily disappear when switching floors because
        # the operator may not exist on the currently visible floor.
        if operator is not None:
            self.current_timeline_row = self._operator_row(operator.operator_id)
        self._refresh_property_panel()
        self._refresh_timeline()

    def _on_operator_transform_started(self) -> None:
        if self._applying_timeline:
            return
        self._pause_column_playback()
        self._operator_transform_history_snapshot = self._capture_history_state()

    def _on_operator_move_finished(self, operator_id: str) -> None:
        before = self._operator_transform_history_snapshot or self._capture_history_state()
        self._operator_transform_history_snapshot = None
        self.current_timeline_row = self._operator_row(operator_id)
        operator = self._current_operator()
        if operator is not None:
            self._update_operator_icon(operator)
            self._refresh_property_panel()
        self._capture_selected_operator_to_current_cell(refresh_history=False)
        self._commit_history(before)

    def _go_to_previous_column(self) -> None:
        self._pause_column_playback()
        if self.current_keyframe_index <= 0:
            return
        self.current_keyframe_index -= 1
        self._apply_column_with_focus_floor(self.current_keyframe_index)

    def _go_to_next_column(self) -> None:
        self._pause_column_playback()
        if self.current_keyframe_index >= len(self.keyframe_columns) - 1:
            return
        self.current_keyframe_index += 1
        self._apply_column_with_focus_floor(self.current_keyframe_index)

    def _start_column_playback(self) -> None:
        if len(self.keyframe_columns) <= 1:
            return
        if self.current_keyframe_index >= len(self.keyframe_columns) - 1:
            self.current_keyframe_index = 0
            self._apply_column_with_focus_floor(self.current_keyframe_index)
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
        self._playback_routes = {}
        self._refresh_timeline()

    def _advance_playback(self) -> None:
        if not self._is_playing or self._playback_to_column < 0:
            return

        scene = self._map_scene()
        if scene is None:
            self._pause_column_playback()
            return

        self._playback_elapsed_ms += self.playback_timer.interval() * self._playback_speed
        progress = min(self._playback_elapsed_ms / self._transition_duration_ms, 1.0)
        self._sync_playback_focus_floor(progress)
        scene.sync_operator_states(self._interpolated_states(progress))
        for operator in scene.operator_items():
            self._update_operator_icon(operator)
        self._sync_scene_preview_paths()
        self._refresh_playback_panel()

        if progress < 1.0:
            return

        self.current_keyframe_index = self._playback_to_column
        self._apply_timeline_column(self.current_keyframe_index)
        if self.current_keyframe_index >= len(self.keyframe_columns) - 1:
            self._pause_column_playback()
        else:
            self._start_transition_to_column(self.current_keyframe_index + 1)
            self._refresh_timeline()

    def _start_transition_to_column(self, target_column: int) -> None:
        if target_column >= len(self.keyframe_columns):
            self._pause_column_playback()
            return
        self._playback_from_column = self.current_keyframe_index
        self._playback_to_column = target_column
        self._playback_elapsed_ms = 0
        self._playback_start_states = self._resolved_state_map(self._playback_from_column)
        self._playback_end_states = self._resolved_state_map(self._playback_to_column)
        self._playback_routes = self._build_transition_routes(
            self._playback_start_states,
            self._playback_end_states,
        )
        self.playback_timer.start()

    def _sync_playback_focus_floor(self, progress: float) -> None:
        operator_id = self._target_operator_id()
        if operator_id is None or not self.current_map_asset_path:
            return

        state = self._interpolated_state_for_operator(operator_id, progress)
        if state is None:
            return

        target_floor_key = state.floor_key or self._current_floor_key()

        if target_floor_key and target_floor_key != self.current_map_floor_key:
            self._load_map_asset(
                self.current_map_asset_path,
                floor_key=target_floor_key,
                fit_view=False,
                pause_playback=False,
            )

    def _apply_column_with_focus_floor(self, column: int) -> None:
        self._sync_focus_floor_for_column(column)
        self._apply_timeline_column(column)

    def _sync_focus_floor_for_column(self, column: int) -> None:
        operator_id = self._target_operator_id()
        if operator_id is None or not self.current_map_asset_path:
            return

        state = self._resolved_state(operator_id, column)
        if state is None:
            return

        target_floor_key = state.floor_key or self._current_floor_key()
        if target_floor_key and target_floor_key != self.current_map_floor_key:
            self._load_map_asset(
                self.current_map_asset_path,
                floor_key=target_floor_key,
                fit_view=False,
                pause_playback=False,
            )

    def _interpolated_states(self, progress: float) -> list[OperatorState]:
        states: list[OperatorState] = []
        for operator_id in self.operator_order:
            state = self._interpolated_state_for_operator(operator_id, progress)
            if state is None or not self._state_matches_current_floor(state):
                continue
            states.append(state)
        return states

    def _interpolated_state_for_operator(self, operator_id: str, progress: float) -> OperatorState | None:
        end_state = self._playback_end_states.get(operator_id)
        start_state = self._playback_start_states.get(operator_id, end_state)
        if start_state is None and end_state is None:
            return None
        if start_state is None:
            start_state = end_state
        if end_state is None:
            end_state = start_state
        if start_state is None or end_state is None:
            return None

        route = self._playback_routes.get(operator_id) or self._build_transition_route_for_operator(
            operator_id,
            start_state,
            end_state,
            self._playback_from_column,
        )
        route_state = self._state_on_route(start_state, end_state, route, progress)
        if route_state is None:
            return None

        rotation_delta = ((end_state.rotation - start_state.rotation + 180) % 360) - 180
        route_state.rotation = start_state.rotation + rotation_delta * progress
        route_state.display_mode = end_state.display_mode
        route_state.custom_name = end_state.custom_name
        route_state.operator_key = end_state.operator_key
        route_state.side = end_state.side
        return route_state

    def _build_transition_routes(
        self,
        start_states: dict[str, OperatorState],
        end_states: dict[str, OperatorState],
    ) -> dict[str, list[PlaybackRouteSegment]]:
        routes: dict[str, list[PlaybackRouteSegment]] = {}
        for operator_id in self.operator_order:
            end_state = end_states.get(operator_id)
            start_state = start_states.get(operator_id, end_state)
            if start_state is None and end_state is None:
                continue
            if start_state is None:
                start_state = end_state
            if end_state is None:
                end_state = start_state
            if start_state is None or end_state is None:
                continue
            routes[operator_id] = self._build_transition_route_for_operator(
                operator_id,
                start_state,
                end_state,
                self._playback_from_column,
            )
        return routes

    def _build_transition_route_for_operator(
        self,
        operator_id: str,
        start_state: OperatorState,
        end_state: OperatorState,
        from_column: int,
    ) -> list[PlaybackRouteSegment]:
        mode, manual_ids = self._transition_settings_for_operator(operator_id, from_column)
        return self._build_transition_route(start_state, end_state, mode, manual_ids)

    def _build_transition_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        transition_mode: OperatorTransitionMode = OperatorTransitionMode.AUTO,
        manual_interaction_ids: list[str] | None = None,
    ) -> list[PlaybackRouteSegment]:
        start_floor = start_state.floor_key or self._current_floor_key()
        end_floor = end_state.floor_key or start_floor
        if start_floor == end_floor:
            return [
                PlaybackRouteSegment(
                    floor_key=start_floor,
                    start=Point2D(start_state.position.x, start_state.position.y),
                    end=Point2D(end_state.position.x, end_state.position.y),
                    result_floor_key=end_floor,
                )
            ]

        interaction_steps = self._find_interaction_route(
            start_state,
            end_state,
            transition_mode=transition_mode,
            manual_interaction_ids=manual_interaction_ids or [],
        )
        if not interaction_steps:
            return [
                PlaybackRouteSegment(
                    floor_key=start_floor,
                    start=Point2D(start_state.position.x, start_state.position.y),
                    end=Point2D(end_state.position.x, end_state.position.y),
                    result_floor_key=end_floor,
                )
            ]

        segments: list[PlaybackRouteSegment] = []
        current_floor = start_floor
        current_point = Point2D(start_state.position.x, start_state.position.y)

        for interaction, target_floor in interaction_steps:
            interaction_point = Point2D(interaction.position.x, interaction.position.y)
            segments.append(
                PlaybackRouteSegment(
                    floor_key=current_floor,
                    start=Point2D(current_point.x, current_point.y),
                    end=Point2D(interaction_point.x, interaction_point.y),
                    result_floor_key=target_floor,
                )
            )
            current_floor = target_floor
            current_point = Point2D(interaction_point.x, interaction_point.y)

        segments.append(
            PlaybackRouteSegment(
                floor_key=end_floor,
                start=Point2D(current_point.x, current_point.y),
                end=Point2D(end_state.position.x, end_state.position.y),
                result_floor_key=end_floor,
            )
        )
        return segments

    def _find_interaction_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        transition_mode: OperatorTransitionMode,
        manual_interaction_ids: list[str],
    ) -> list[tuple[MapInteractionPoint, str]]:
        if self._current_map_asset is None or not self._current_map_asset.interactions:
            return []

        start_floor = start_state.floor_key or self._current_floor_key()
        end_floor = end_state.floor_key or start_floor
        if start_floor == end_floor:
            return []

        if transition_mode == OperatorTransitionMode.MANUAL and manual_interaction_ids:
            manual_prefix = self._manual_interaction_prefix(start_floor, manual_interaction_ids)
            if manual_prefix is not None:
                route_prefix, current_floor = manual_prefix
                if current_floor == end_floor:
                    return route_prefix

                prefix_point = Point2D(start_state.position.x, start_state.position.y)
                if route_prefix:
                    last_interaction, _ = route_prefix[-1]
                    prefix_point = Point2D(last_interaction.position.x, last_interaction.position.y)

                continuation_start = self._copy_state_with_position(
                    start_state,
                    prefix_point,
                    current_floor,
                )
                suffix = self._find_automatic_interaction_route(continuation_start, end_state)
                if suffix:
                    return route_prefix + suffix

        return self._find_automatic_interaction_route(start_state, end_state)

    def _find_automatic_interaction_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
    ) -> list[tuple[MapInteractionPoint, str]]:
        start_floor = start_state.floor_key or self._current_floor_key()
        end_floor = end_state.floor_key or start_floor
        if start_floor == end_floor:
            return []

        goal_key = ("goal", "")
        start_key = ("start", start_floor)
        best_costs: dict[tuple[str, str], float] = {start_key: 0.0}
        parents: dict[tuple[str, str], tuple[tuple[str, str], MapInteractionPoint | None, str]] = {}
        node_positions: dict[tuple[str, str], Point2D] = {
            start_key: Point2D(start_state.position.x, start_state.position.y)
        }
        heap: list[tuple[float, str, str]] = [(0.0, start_key[0], start_key[1])]

        while heap:
            current_cost, current_kind, current_floor = heappop(heap)
            current_key = (current_kind, current_floor)
            if current_cost > best_costs.get(current_key, float("inf")):
                continue
            if current_key == goal_key:
                break

            current_point = node_positions[current_key]
            if current_floor == end_floor:
                goal_cost = current_cost + self._distance_points(current_point, end_state.position)
                if goal_cost < best_costs.get(goal_key, float("inf")):
                    best_costs[goal_key] = goal_cost
                    parents[goal_key] = (current_key, None, end_floor)
                    node_positions[goal_key] = Point2D(end_state.position.x, end_state.position.y)
                    heappush(heap, (goal_cost, goal_key[0], goal_key[1]))

            for interaction, target_floor in self._iter_interaction_transitions(current_floor):
                next_key = (interaction.id, target_floor)
                interaction_point = Point2D(interaction.position.x, interaction.position.y)
                travel_cost = self._distance_points(current_point, interaction_point)
                next_cost = current_cost + travel_cost
                if next_cost >= best_costs.get(next_key, float("inf")):
                    continue
                best_costs[next_key] = next_cost
                parents[next_key] = (current_key, interaction, target_floor)
                node_positions[next_key] = Point2D(interaction.position.x, interaction.position.y)
                heappush(heap, (next_cost, next_key[0], next_key[1]))

        if goal_key not in parents:
            return []

        steps: list[tuple[MapInteractionPoint, str]] = []
        current_key = goal_key
        while current_key != start_key:
            parent_key, interaction, target_floor = parents[current_key]
            if interaction is not None:
                steps.append((interaction, target_floor))
            current_key = parent_key
        steps.reverse()
        return steps

    def _manual_interaction_route(
        self,
        start_floor: str,
        end_floor: str,
        manual_interaction_ids: list[str],
    ) -> list[tuple[MapInteractionPoint, str]]:
        if not manual_interaction_ids:
            return []
        manual_prefix = self._manual_interaction_prefix(start_floor, manual_interaction_ids)
        if manual_prefix is None:
            return []
        route, current_floor = manual_prefix
        return route if current_floor == end_floor else []

    @staticmethod
    def _resolve_manual_target_floor(
        interaction: MapInteractionPoint,
        current_floor: str,
    ) -> str | None:
        if interaction.floor_key == current_floor:
            return interaction.linked_floor_keys[0] if interaction.linked_floor_keys else None
        if interaction.is_bidirectional and current_floor in interaction.linked_floor_keys:
            return interaction.floor_key
        return None

    def _transition_settings_for_operator(
        self,
        operator_id: str,
        from_column: int,
    ) -> tuple[OperatorTransitionMode, list[str]]:
        frame = self._resolved_frame_state(operator_id, from_column)
        if frame is None:
            return (OperatorTransitionMode.AUTO, [])
        return (frame.transition_mode, list(frame.manual_interaction_ids))

    def _iter_interaction_transitions(self, floor_key: str) -> list[tuple[MapInteractionPoint, str]]:
        if self._current_map_asset is None:
            return []

        transitions: list[tuple[MapInteractionPoint, str]] = []
        for interaction in self._current_map_asset.interactions:
            if interaction.floor_key == floor_key:
                for target_floor in interaction.linked_floor_keys:
                    transitions.append((interaction, target_floor))
            elif interaction.is_bidirectional and floor_key in interaction.linked_floor_keys:
                transitions.append((interaction, interaction.floor_key))
        return transitions

    def _state_on_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list[PlaybackRouteSegment],
        progress: float,
    ) -> OperatorState:
        total_length = sum(self._route_segment_length(segment) for segment in route)
        if total_length <= 0.001:
            return deepcopy(end_state)

        target_distance = total_length * progress
        traveled = 0.0
        current_floor = start_state.floor_key or self._current_floor_key()
        current_point = Point2D(start_state.position.x, start_state.position.y)

        for segment in route:
            length = self._route_segment_length(segment)
            if length <= 0.001:
                if target_distance <= traveled:
                    return self._copy_state_with_position(
                        start_state,
                        current_point,
                        current_floor,
                    )
                current_floor = segment.result_floor_key or current_floor
                current_point = Point2D(segment.end.x, segment.end.y)
                continue

            if target_distance <= traveled + length or segment is route[-1]:
                local_progress = max(0.0, min(1.0, (target_distance - traveled) / length))
                position = Point2D(
                    x=segment.start.x + (segment.end.x - segment.start.x) * local_progress,
                    y=segment.start.y + (segment.end.y - segment.start.y) * local_progress,
                )
                floor_key = segment.floor_key
                if local_progress >= 1.0 and segment.result_floor_key:
                    floor_key = segment.result_floor_key
                return self._copy_state_with_position(end_state, position, floor_key)

            traveled += length
            current_floor = segment.result_floor_key or current_floor
            current_point = Point2D(segment.end.x, segment.end.y)

        return deepcopy(end_state)

    @staticmethod
    def _copy_state_with_position(
        template: OperatorState,
        position: Point2D,
        floor_key: str,
    ) -> OperatorState:
        return OperatorState(
            id=template.id,
            operator_key=template.operator_key,
            custom_name=template.custom_name,
            side=template.side,
            position=Point2D(position.x, position.y),
            rotation=template.rotation,
            display_mode=template.display_mode,
            floor_key=floor_key,
        )

    @staticmethod
    def _route_segment_length(segment: PlaybackRouteSegment) -> float:
        return hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y)

    @staticmethod
    def _distance_points(first: Point2D, second: Point2D) -> float:
        return hypot(second.x - first.x, second.y - first.y)

    def _set_transition_duration(self, value: int) -> None:
        self._transition_duration_ms = value
        if self.playback_duration_slider.value() != value:
            self.playback_duration_slider.blockSignals(True)
            self.playback_duration_slider.setValue(value)
            self.playback_duration_slider.blockSignals(False)
        self._refresh_playback_panel()

    def _update_current_keyframe_name(self, name: str) -> None:
        if self._syncing_keyframe_panel:
            return
        if not (0 <= self.current_keyframe_index < len(self.keyframe_names)):
            return
        normalized = name.strip()
        if normalized == self.keyframe_names[self.current_keyframe_index]:
            return
        before = self._capture_history_state()
        self.keyframe_names[self.current_keyframe_index] = normalized
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _update_current_keyframe_note(self, note: str) -> None:
        if self._syncing_keyframe_panel:
            return
        if not (0 <= self.current_keyframe_index < len(self.keyframe_notes)):
            return
        normalized = note.strip()
        if normalized == self.keyframe_notes[self.current_keyframe_index]:
            return
        before = self._capture_history_state()
        self.keyframe_notes[self.current_keyframe_index] = normalized
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _move_keyframe_column(self, from_index: int, to_index: int) -> None:
        if not (0 <= from_index < len(self.keyframe_columns) and 0 <= to_index < len(self.keyframe_columns)):
            return
        if from_index == to_index:
            return
        before = self._capture_history_state()
        self._pause_column_playback()
        column = self.keyframe_columns.pop(from_index)
        self.keyframe_columns.insert(to_index, column)
        keyframe_name = self.keyframe_names.pop(from_index)
        keyframe_note = self.keyframe_notes.pop(from_index)
        self.keyframe_names.insert(to_index, keyframe_name)
        self.keyframe_notes.insert(to_index, keyframe_note)
        self.current_keyframe_index = self._moved_index(self.current_keyframe_index, from_index, to_index)
        self._apply_timeline_column(self.current_keyframe_index)
        self._refresh_timeline()
        self._commit_history(before)

    def _move_operator_row(self, from_index: int, to_index: int) -> None:
        if not (0 <= from_index < len(self.operator_order) and 0 <= to_index < len(self.operator_order)):
            return
        if from_index == to_index:
            return
        before = self._capture_history_state()
        operator_id = self.operator_order.pop(from_index)
        self.operator_order.insert(to_index, operator_id)
        self.current_timeline_row = self._moved_index(self.current_timeline_row, from_index, to_index)
        self._refresh_timeline()
        self._commit_history(before)

    def _delete_operator_row(self, row: int) -> None:
        if not (0 <= row < len(self.operator_order)):
            return
        self._delete_operator_by_id(self.operator_order[row], confirm=True)

    def _sync_scene_placement_target(self) -> None:
        scene = self._map_scene()
        if scene is None:
            return
        scene.set_placement_state(self._current_placement_state())

    def _sync_scene_preview_paths(self) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        preview_paths: dict[str, tuple[QPointF, QPointF]] = {}
        for operator_id, (start_state, end_state) in self._current_preview_segments().items():
            if self._same_position(start_state, end_state):
                continue
            preview_paths[operator_id] = (
                QPointF(start_state.position.x, start_state.position.y),
                QPointF(end_state.position.x, end_state.position.y),
            )

        scene.set_preview_paths(preview_paths)

    def _current_preview_segments(self) -> dict[str, tuple[OperatorState, OperatorState]]:
        if self._is_playing and self._playback_from_column >= 0 and self._playback_to_column >= 0:
            progress = min(self._playback_elapsed_ms / max(self._transition_duration_ms, 1), 1.0)
            return self._preview_segments_for_columns(
                self._playback_from_column,
                self._playback_to_column,
                progress=progress,
            )

        next_column = self.current_keyframe_index + 1
        if next_column >= len(self.keyframe_columns):
            return {}
        return self._preview_segments_for_columns(self.current_keyframe_index, next_column, progress=0.0)

    def _preview_segments_for_columns(
        self,
        from_column: int,
        to_column: int,
        progress: float,
    ) -> dict[str, tuple[OperatorState, OperatorState]]:
        segments: dict[str, tuple[OperatorState, OperatorState]] = {}
        for operator_id in self.operator_order:
            start_state = self._resolved_state(operator_id, from_column)
            end_state = self._resolved_state(operator_id, to_column)
            if start_state is None or end_state is None:
                continue
            route = self._playback_routes.get(operator_id)
            if route is None:
                route = self._build_transition_route_for_operator(
                    operator_id,
                    start_state,
                    end_state,
                    from_column,
                )
            preview = self._preview_segment_on_route(start_state, end_state, route, progress)
            if preview is None:
                continue
            segments[operator_id] = preview
        return segments

    def _preview_segment_on_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list[PlaybackRouteSegment],
        progress: float,
    ) -> tuple[OperatorState, OperatorState] | None:
        if not route:
            if not self._state_matches_current_floor(start_state) or not self._state_matches_current_floor(end_state):
                return None
            return (start_state, end_state)

        total_length = sum(self._route_segment_length(segment) for segment in route)
        if total_length <= 0.001:
            return None

        target_distance = total_length * progress
        traveled = 0.0
        for segment in route:
            length = self._route_segment_length(segment)
            if length <= 0.001:
                continue
            if target_distance <= traveled + length or segment is route[-1]:
                if segment.floor_key != self._current_floor_key():
                    return None
                segment_start = self._copy_state_with_position(start_state, segment.start, segment.floor_key)
                segment_end = self._copy_state_with_position(end_state, segment.end, segment.floor_key)
                return (segment_start, segment_end)
            traveled += length
        return None

    def _current_placement_state(self) -> OperatorState | None:
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return None
        if not (0 <= self.current_timeline_row < len(self.operator_order)):
            return None

        operator_id = self.operator_order[self.current_timeline_row]
        definition = self.operator_definitions.get(operator_id)
        frame = self._resolved_frame_state(operator_id, self.current_keyframe_index)
        if definition is not None and frame is not None:
            frame = deepcopy(frame)
            frame.floor_key = self._current_floor_key()
            return resolve_operator_state(definition, frame)

        scene = self._map_scene()
        operator = scene.find_operator(operator_id) if scene is not None else None
        if operator is not None and definition is not None:
            current_frame = self._frame_state_from_operator(operator)
            if current_frame is not None:
                return resolve_operator_state(definition, current_frame)

        if definition is not None:
            return resolve_operator_state(
                definition,
                OperatorFrameState(
                    id=operator_id,
                    position=Point2D(x=0, y=0),
                    rotation=0,
                    display_mode=OperatorDisplayMode.ICON,
                    floor_key=self._current_floor_key(),
                ),
            )

        return None

    @staticmethod
    def _same_position(first: OperatorState, second: OperatorState) -> bool:
        return (
            abs(first.position.x - second.position.x) < 0.1
            and abs(first.position.y - second.position.y) < 0.1
        )

    def _current_floor_key(self) -> str:
        return self.current_map_floor_key or "default"

    def _state_matches_current_floor(self, state: OperatorState) -> bool:
        if not state.floor_key:
            return True
        return state.floor_key == self._current_floor_key()

    def _operator_label(self, operator_id: str) -> str:
        definition = self.operator_definitions.get(operator_id)
        if definition is None or not definition.custom_name:
            return f"干员 {operator_id}"
        return definition.custom_name

    def _target_operator_id(self) -> str | None:
        if 0 <= self.current_timeline_row < len(self.operator_order):
            return self.operator_order[self.current_timeline_row]
        return None

    def _keyframe_label(self, index: int) -> str:
        if 0 <= index < len(self.keyframe_names) and self.keyframe_names[index]:
            return self.keyframe_names[index]
        return f"K{index + 1}"

    def _current_keyframe_name(self) -> str:
        if 0 <= self.current_keyframe_index < len(self.keyframe_names):
            return self.keyframe_names[self.current_keyframe_index]
        return ""

    def _current_keyframe_note(self) -> str:
        if 0 <= self.current_keyframe_index < len(self.keyframe_notes):
            return self.keyframe_notes[self.current_keyframe_index]
        return ""

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
                self.operator_definitions[operator.operator_id] = OperatorDefinition(
                    id=operator.operator_id,
                    custom_name=operator.custom_name,
                    side=TeamSide(operator.side),
                    operator_key=operator.operator_key,
                )

        state_ids = {
            operator_id
            for frame in self.keyframe_columns
            for operator_id in frame
        }
        all_ids = sorted(
            set(scene_ids) | state_ids | set(self.operator_definitions),
            key=self._sort_operator_id,
        )
        self.operator_order = all_ids

        for operator_id in list(self.operator_definitions):
            if operator_id not in all_ids:
                del self.operator_definitions[operator_id]

    def _remove_operator_from_timeline(self, operator_id: str) -> None:
        for frame in self.keyframe_columns:
            frame.pop(operator_id, None)
        self.operator_definitions.pop(operator_id, None)

    def _delete_operator_by_id(self, operator_id: str, confirm: bool) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        if confirm:
            dialog = MessageBox("删除干员", f"确定删除干员 {operator_id} 吗？", self)
            dialog.yesButton.setText("确定")
            dialog.cancelButton.setText("取消")
            if not dialog.exec():
                return

        before = self._capture_history_state()
        self._pause_column_playback()
        operator = scene.find_operator(operator_id)
        if operator is not None:
            scene.removeItem(operator)
        self._remove_operator_from_timeline(operator_id)
        self.current_timeline_row = -1
        self._sync_operator_registry()
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _frame_state_from_operator(self, operator: OperatorItem) -> OperatorFrameState | None:
        display_mode = (
            OperatorDisplayMode.ICON
            if operator.display_mode == OperatorItem.ICON
            else OperatorDisplayMode.CUSTOM_NAME
        )
        current_frame = self._current_transition_frame(operator.operator_id)
        return OperatorFrameState(
            id=operator.operator_id,
            position=Point2D(x=operator.pos().x(), y=operator.pos().y()),
            rotation=operator.rotation(),
            display_mode=display_mode,
            floor_key=self._current_floor_key(),
            transition_mode=(
                current_frame.transition_mode
                if current_frame is not None
                else OperatorTransitionMode.AUTO
            ),
            manual_interaction_ids=(
                list(current_frame.manual_interaction_ids)
                if current_frame is not None
                else []
            ),
        )

    def _apply_global_operator_metadata(
        self,
        operator_id: str,
        *,
        custom_name: str | None = None,
        side: str | None = None,
        operator_key: str | None = None,
    ) -> None:
        scene = self._map_scene()
        operator = scene.find_operator(operator_id) if scene is not None else None
        definition = self.operator_definitions.get(operator_id)
        if definition is None:
            definition = OperatorDefinition(
                id=operator_id,
                custom_name=operator.custom_name if operator is not None else f"干员 {operator_id}",
                side=TeamSide(operator.side) if operator is not None else TeamSide.ATTACK,
                operator_key=operator.operator_key if operator is not None else "",
            )

        if custom_name is not None:
            definition.custom_name = custom_name
        if side is not None:
            definition.side = TeamSide(side)
        if operator_key is not None:
            definition.operator_key = operator_key

        self.operator_definitions[operator_id] = definition

        if operator is not None:
            operator.set_custom_name(definition.custom_name)
            operator.set_side(definition.side.value)
            operator.set_operator_key(definition.operator_key)
            self._update_operator_icon(operator)

    def _build_project(self) -> TacticProject:
        scene = self._map_scene()
        map_info = None
        if scene is not None and scene.current_map_path:
            map_path = Path(scene.current_map_path)
            if self._current_map_asset is not None:
                map_info = MapInfo(
                    key=self._current_map_asset.key,
                    name=self._current_map_asset.name,
                    image_path=str(map_path),
                    metadata_path=self.current_map_asset_path,
                    current_floor_key=self.current_map_floor_key,
                )
            else:
                map_info = MapInfo(key=map_path.stem, name=map_path.name, image_path=str(map_path))

        operators = [
            deepcopy(self.operator_definitions[operator_id])
            for operator_id in self.operator_order
            if operator_id in self.operator_definitions
        ]
        keyframes = [
            Keyframe(
                time_ms=index * self._transition_duration_ms,
                name=self.keyframe_names[index] if index < len(self.keyframe_names) else "",
                note=self.keyframe_notes[index] if index < len(self.keyframe_notes) else "",
                operator_frames=[deepcopy(frame[operator_id]) for operator_id in self.operator_order if operator_id in frame],
            )
            for index, frame in enumerate(self.keyframe_columns)
        ]
        return TacticProject(
            name=Path(self.current_project_path).stem if self.current_project_path else "untitled",
            map_info=map_info,
            operators=operators,
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

        if project.map_info and project.map_info.metadata_path:
            if not self._load_map_asset(
                project.map_info.metadata_path,
                floor_key=project.map_info.current_floor_key,
            ):
                scene.clear_map()
                self.map_status_label.setText("当前地图：加载失败")
                self.current_map_asset_path = ""
                self.current_map_floor_key = ""
                self._current_map_asset = None
                self._rebuild_floor_panel()
        elif project.map_info and project.map_info.image_path:
            if scene.load_map_image(project.map_info.image_path):
                self.map_status_label.setText(f"当前地图：{Path(project.map_info.image_path).name}")
                self.map_view.fit_scene()
                self.current_map_asset_path = ""
                self.current_map_floor_key = ""
                self._current_map_asset = None
                self._rebuild_floor_panel()
            else:
                self.map_status_label.setText("当前地图：加载失败")
        else:
            scene.clear_map()
            self.map_status_label.setText("当前地图：未加载")
            self.current_map_asset_path = ""
            self.current_map_floor_key = ""
            self._current_map_asset = None
            self._rebuild_floor_panel()

        self.operator_order = list(project.operator_order)
        self.operator_definitions = {
            operator.id: deepcopy(operator)
            for operator in project.operators
        }
        self.keyframe_columns = [
            {state.id: deepcopy(state) for state in keyframe.operator_frames}
            for keyframe in project.timeline.keyframes
        ] or [{}]
        self.keyframe_names = [keyframe.name for keyframe in project.timeline.keyframes] or [""]
        self.keyframe_notes = [keyframe.note for keyframe in project.timeline.keyframes] or [""]
        self.current_keyframe_index = min(project.current_keyframe_index, len(self.keyframe_columns) - 1)
        self.current_timeline_row = -1
        self._transition_duration_ms = project.transition_duration_ms
        self.playback_duration_slider.setValue(self._transition_duration_ms)

        for operator_id in self.operator_definitions:
            if operator_id not in self.operator_order:
                self.operator_order.append(operator_id)
        for frame in self.keyframe_columns:
            for state in frame.values():
                if state.id not in self.operator_order:
                    self.operator_order.append(state.id)

        self._apply_timeline_column(self.current_keyframe_index)
        self._refresh_timeline()

    def _capture_history_state(self) -> EditorHistoryState:
        scene = self._map_scene()
        selected = self._current_operator()
        return EditorHistoryState(
            map_asset_path=self.current_map_asset_path,
            map_floor_key=self.current_map_floor_key,
            map_image_path=scene.current_map_path if scene is not None else "",
            scene_states=deepcopy(scene.snapshot_operator_states() if scene is not None else []),
            selected_operator_id=selected.operator_id if selected is not None else "",
            operator_order=list(self.operator_order),
            operator_definitions=deepcopy(self.operator_definitions),
            keyframe_columns=deepcopy(self.keyframe_columns),
            keyframe_names=list(self.keyframe_names),
            keyframe_notes=list(self.keyframe_notes),
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
        if snapshot.map_asset_path:
            if not self._load_map_asset(snapshot.map_asset_path, floor_key=snapshot.map_floor_key, fit_view=False):
                scene.clear_map()
                self.map_status_label.setText("当前地图：加载失败")
                self.current_map_asset_path = ""
                self.current_map_floor_key = ""
                self._current_map_asset = None
                self._rebuild_floor_panel()
        else:
            if snapshot.map_image_path:
                scene.load_map_image(snapshot.map_image_path)
                self.map_status_label.setText(f"当前地图：{Path(snapshot.map_image_path).name}")
            else:
                scene.clear_map()
                self.map_status_label.setText("当前地图：未加载")
            self.current_map_asset_path = ""
            self.current_map_floor_key = ""
            self._current_map_asset = None
            self._rebuild_floor_panel()

        self.operator_order = list(snapshot.operator_order)
        self.operator_definitions = deepcopy(snapshot.operator_definitions)
        self.keyframe_columns = deepcopy(snapshot.keyframe_columns)
        self.keyframe_names = list(snapshot.keyframe_names)
        self.keyframe_notes = list(snapshot.keyframe_notes)
        self.current_keyframe_index = snapshot.current_keyframe_index
        self.current_timeline_row = snapshot.current_timeline_row
        self._transition_duration_ms = snapshot.transition_duration_ms
        self.playback_duration_slider.setValue(self._transition_duration_ms)

        scene.sync_operator_states(deepcopy(snapshot.scene_states), snapshot.selected_operator_id or None)
        for operator in scene.operator_items():
            self._update_operator_icon(operator)

        self._refresh_property_panel()
        self._history_lock = False
        self._refresh_timeline()

    @staticmethod
    def _moved_index(current_index: int, from_index: int, to_index: int) -> int:
        if current_index == from_index:
            return to_index
        if from_index < current_index <= to_index:
            return current_index - 1
        if to_index <= current_index < from_index:
            return current_index + 1
        return current_index

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
