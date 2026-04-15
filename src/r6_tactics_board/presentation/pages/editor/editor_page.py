from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    MessageBox,
    PrimaryPushButton,
    PushButton,
)

from r6_tactics_board.application.routing.interaction_routing import (
    InteractionRoutePlanner,
    PlaybackRouteSegment,
)
from r6_tactics_board.application.services.editor_session import EditorSessionService
from r6_tactics_board.application.state.history import UndoRedoHistory
from r6_tactics_board.application.timeline.timeline_editor import TimelineEditorController
from r6_tactics_board.domain.models import (
    MapInteractionPoint,
    MapInteractionType,
    MapSurface,
    MapSurfaceType,
    OperatorDefinition,
    OperatorDisplayMode,
    OperatorFrameState,
    OperatorState,
    OperatorTransitionMode,
    Point2D,
    SurfaceOpeningType,
    TacticalSurfaceState,
    TacticProject,
    TeamSide,
    resolve_operator_state,
)
from r6_tactics_board.infrastructure.assets.asset_paths import MAPS_DIR
from r6_tactics_board.infrastructure.assets.asset_registry import MapAsset
from r6_tactics_board.infrastructure.diagnostics.debug_logging import debug_log
from r6_tactics_board.presentation.pages.editor.editor_models import EditorHistoryState, EditorProjectState
from r6_tactics_board.presentation.pages.editor.editor_tokens import EditorTokenWorkflowMixin
from r6_tactics_board.presentation.styles.theme import page_stylesheet
from r6_tactics_board.presentation.widgets.editor.editor_panels import (
    EditorPropertyPanel,
    FloorOverlayPanel,
    PlaybackOverlayPanel,
)
from r6_tactics_board.presentation.widgets.canvas.map_scene import MapScene
from r6_tactics_board.presentation.widgets.canvas.map_view import MapView
from r6_tactics_board.presentation.widgets.canvas.operator_item import OperatorItem
from r6_tactics_board.presentation.widgets.canvas.overview_scene import OverviewScene
from r6_tactics_board.presentation.widgets.canvas.overview_view import OverviewView
from r6_tactics_board.presentation.widgets.timeline.timeline_widget import TimelineWidget


class EditorPage(EditorTokenWorkflowMixin, QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("editor-page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("themePage", True)

        self._syncing_panel = False
        self._syncing_keyframe_panel = False
        self._applying_timeline = False
        self._is_playing = False
        self._history_lock = False
        self._rotation_history_snapshot: EditorHistoryState | None = None
        self._operator_transform_history_snapshot: EditorHistoryState | None = None
        self._operator_size_history_snapshot: EditorHistoryState | None = None
        self._gadget_transform_history_snapshot: EditorHistoryState | None = None
        self._playback_from_column = -1
        self._playback_to_column = -1
        self._playback_elapsed_ms = 0.0
        self._playback_effective_duration_ms = 700.0
        self._playback_speed = 1.0
        self._scrubbing_playback_slider = False
        self._hovered_manual_interaction_id = ""
        self._property_panel_refresh_pending = False
        self._syncing_property_section = False
        self._preferred_property_section = "operator"
        self._last_property_auto_context: tuple[str, str] | None = None
        self._transition_duration_ms = 700
        self._playback_start_states: dict[str, OperatorState] = {}
        self._playback_end_states: dict[str, OperatorState] = {}
        self._playback_routes: dict[str, list[PlaybackRouteSegment]] = {}
        self._placing_gadget = False
        self._placing_ability = False
        self._history = UndoRedoHistory[EditorHistoryState](limit=100)

        self.operator_order: list[str] = []
        self.operator_definitions: dict[str, OperatorDefinition] = {}
        self.keyframe_columns: list[dict[str, OperatorFrameState]] = [{}]
        self.keyframe_names: list[str] = [""]
        self.keyframe_notes: list[str] = [""]
        self.current_keyframe_index = 0
        self.current_timeline_row = -1
        self.current_surface_id = ""
        self.current_project_path = ""
        self.current_map_asset_path = ""
        self.current_map_floor_key = ""
        self._current_map_asset: MapAsset | None = None
        self._overview_visible_floor_keys: set[str] = set()
        self._clean_project_state: EditorProjectState | None = None
        self.surface_states: dict[str, TacticalSurfaceState] = {}
        self._operator_scale = 1.0

        self.session_service = EditorSessionService()
        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(16)

        self._view_mode = "single_floor"
        self.map_view = MapView()
        self.overview_view = OverviewView()
        self.canvas_stack = QStackedWidget()
        self.timeline = TimelineWidget()
        self.undo_button = PushButton("撤销")
        self.redo_button = PushButton("重做")
        self.open_project_button = PushButton("打开工程")
        self.save_project_button = PushButton("保存工程")
        self.load_map_button = PrimaryPushButton("加载地图")
        self.add_operator_button = PushButton("添加干员")
        self.reset_view_button = PushButton("重置视图")
        self.map_status_label = BodyLabel("当前地图：未加载")
        self.view_mode_label = BodyLabel("视图")
        self.view_mode_combo = ComboBox()
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.property_panel = EditorPropertyPanel()
        self.floor_panel = FloorOverlayPanel(self)
        self.playback_panel = PlaybackOverlayPanel(initial_duration_ms=self._transition_duration_ms, parent=self)

        self.property_title = self.property_panel.property_title
        self.property_hint = self.property_panel.property_hint
        self.selection_label = self.property_panel.selection_label
        self.keyframe_title = self.property_panel.keyframe_title
        self.keyframe_hint = self.property_panel.keyframe_hint
        self.keyframe_name_edit = self.property_panel.keyframe_name_edit
        self.keyframe_note_edit = self.property_panel.keyframe_note_edit
        self.name_edit = self.property_panel.name_edit
        self.side_combo = self.property_panel.side_combo
        self.operator_combo = self.property_panel.operator_combo
        self.rotation_slider = self.property_panel.rotation_slider
        self.rotation_value_label = self.property_panel.rotation_value_label
        self.floor_value_label = self.property_panel.floor_value_label
        self.gadget_label = self.property_panel.gadget_label
        self.gadget_combo = self.property_panel.gadget_combo
        self.gadget_count_label = self.property_panel.gadget_count_label
        self.place_gadget_button = self.property_panel.place_gadget_button
        self.clear_gadget_button = self.property_panel.clear_gadget_button
        self.ability_label = self.property_panel.ability_label
        self.ability_name_label = self.property_panel.ability_name_label
        self.ability_count_label = self.property_panel.ability_count_label
        self.place_ability_button = self.property_panel.place_ability_button
        self.clear_ability_button = self.property_panel.clear_ability_button
        self.transition_mode_label = self.property_panel.transition_mode_label
        self.manual_interaction_label = self.property_panel.manual_interaction_label
        self.show_icon_box = self.property_panel.show_icon_box
        self.show_name_box = self.property_panel.show_name_box
        self.operator_size_slider = self.property_panel.operator_size_slider
        self.operator_size_value_label = self.property_panel.operator_size_value_label
        self.transition_mode_combo = self.property_panel.transition_mode_combo
        self.manual_interactions_hint = self.property_panel.manual_interactions_hint
        self.manual_interaction_combo = self.property_panel.manual_interaction_combo
        self.delete_operator_button = self.property_panel.delete_operator_button
        self.surface_title = self.property_panel.surface_title
        self.surface_hint = self.property_panel.surface_hint
        self.surface_selection_label = self.property_panel.surface_selection_label
        self.surface_count_label = self.property_panel.surface_count_label
        self.reinforce_button = self.property_panel.reinforce_button
        self.surface_opening_label = self.property_panel.surface_opening_label
        self.opening_combo = self.property_panel.opening_combo
        self.foot_hole_box = self.property_panel.foot_hole_box
        self.gun_hole_box = self.property_panel.gun_hole_box
        self.playback_previous_button = self.playback_panel.previous_button
        self.playback_play_button = self.playback_panel.play_button
        self.playback_pause_button = self.playback_panel.pause_button
        self.playback_next_button = self.playback_panel.next_button
        self.playback_progress_slider = self.playback_panel.progress_slider
        self.playback_status_label = self.playback_panel.status_label
        self.playback_speed_combo = self.playback_panel.speed_combo
        self.playback_duration_label = self.playback_panel.duration_label
        self.playback_duration_slider = self.playback_panel.duration_slider
        self.view_mode_combo.addItem("单楼层")
        self.view_mode_combo.setItemData(0, "single_floor")
        self.view_mode_combo.addItem("2.5D 总览")
        self.view_mode_combo.setItemData(1, "overview_2p5d")
        self.view_mode_combo.setCurrentIndex(0)
        self.view_mode_combo.setEnabled(False)

        self._init_ui()
        self._init_signals()
        self._sync_gadget_catalog()
        self._sync_operator_registry()
        self._refresh_property_panel()
        self._refresh_timeline()
        self._reset_history(mark_clean=True)

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
        toolbar_layout.addWidget(self.view_mode_label)
        toolbar_layout.addWidget(self.view_mode_combo)
        toolbar_layout.addWidget(self.map_status_label, 1)

        self.canvas_stack.addWidget(self.map_view)
        self.canvas_stack.addWidget(self.overview_view)
        center_layout.addLayout(toolbar_layout)
        center_layout.addWidget(self.canvas_stack, 1)
        center_layout.addWidget(self.timeline)

        layout.addLayout(center_layout, 1)
        layout.addWidget(self.property_panel)

    def _init_signals(self) -> None:
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        self.undo_shortcut.activated.connect(self.undo)
        self.redo_shortcut.activated.connect(self.redo)
        self.load_map_button.clicked.connect(self._load_map)
        self.open_project_button.clicked.connect(self._open_project)
        self.save_project_button.clicked.connect(self._save_project)
        self.add_operator_button.clicked.connect(self._add_operator)
        self.reset_view_button.clicked.connect(self._reset_active_view)
        self.delete_operator_button.clicked.connect(self._delete_selected_operator)
        self.name_edit.editingFinished.connect(self._apply_name_edit)
        self.side_combo.currentIndexChanged.connect(self._update_selected_side)
        self.operator_combo.currentIndexChanged.connect(self._update_selected_operator_asset)
        self.gadget_combo.currentIndexChanged.connect(self._update_selected_gadget_asset)
        self.place_gadget_button.toggled.connect(self._toggle_gadget_placement_mode)
        self.clear_gadget_button.clicked.connect(self._clear_current_frame_gadget_placements)
        self.place_ability_button.toggled.connect(self._toggle_ability_placement_mode)
        self.clear_ability_button.clicked.connect(self._clear_current_frame_ability_placements)
        self.rotation_slider.sliderPressed.connect(self._on_rotation_slider_pressed)
        self.rotation_slider.sliderReleased.connect(self._on_rotation_slider_released)
        self.rotation_slider.valueChanged.connect(self._update_selected_rotation)
        self.show_icon_box.toggled.connect(self._update_show_icon)
        self.show_name_box.toggled.connect(self._update_show_name)
        self.operator_size_slider.sliderPressed.connect(self._on_operator_size_slider_pressed)
        self.operator_size_slider.sliderReleased.connect(self._on_operator_size_slider_released)
        self.operator_size_slider.valueChanged.connect(self._update_operator_scale)
        self.transition_mode_combo.currentIndexChanged.connect(self._update_transition_mode)
        self.reinforce_button.clicked.connect(self._toggle_selected_surface_reinforcement)
        self.opening_combo.currentIndexChanged.connect(self._update_selected_surface_opening)
        self.foot_hole_box.toggled.connect(self._update_selected_surface_foot_hole)
        self.gun_hole_box.toggled.connect(self._update_selected_surface_gun_hole)
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
        self.timeline.keyframe_selected.connect(self._select_keyframe_column)
        self.timeline.keyframe_column_moved.connect(self._move_keyframe_column)
        self.timeline.operator_row_moved.connect(self._move_operator_row)
        self.playback_timer.timeout.connect(self._advance_playback)
        self.map_view.viewport_resized.connect(self._position_overlay_panels)
        self.overview_view.viewport_resized.connect(self._position_overlay_panels)
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        self.playback_previous_button.clicked.connect(self._go_to_previous_column)
        self.playback_next_button.clicked.connect(self._go_to_next_column)
        self.playback_play_button.clicked.connect(self._toggle_column_playback)
        self.playback_duration_slider.valueChanged.connect(self._set_transition_duration)
        self.playback_speed_combo.currentIndexChanged.connect(self._update_playback_speed)
        self.manual_interaction_combo.activated.connect(self._select_manual_interaction_candidate)
        self.manual_interaction_combo.highlighted.connect(self._preview_manual_interaction_hover)
        self.manual_interaction_combo.popupHidden.connect(self._on_manual_interaction_popup_hidden)
        self.property_panel.section_tabs.currentChanged.connect(self._on_property_section_changed)
        self.playback_progress_slider.sliderPressed.connect(self._on_playback_slider_pressed)
        self.playback_progress_slider.sliderMoved.connect(self._on_playback_slider_moved)
        self.playback_progress_slider.sliderReleased.connect(self._on_playback_slider_released)

        scene = self._map_scene()
        if scene is not None:
            scene.selectionChanged.connect(self._on_scene_selection_changed)
            scene.operator_transform_started.connect(self._on_operator_transform_started)
            scene.operator_move_finished.connect(self._on_operator_move_finished)
            scene.gadget_transform_started.connect(self._on_gadget_transform_started)
            scene.gadget_move_finished.connect(self._on_gadget_move_finished)
            scene.gadget_placed.connect(self._on_gadget_placed)
            scene.ability_transform_started.connect(self._on_ability_transform_started)
            scene.ability_move_finished.connect(self._on_ability_move_finished)
            scene.ability_placed.connect(self._on_ability_placed)
            scene.surface_selected.connect(self._on_surface_selected)

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
        previous_project_path = self.current_project_path
        self._pause_column_playback()
        self._reset_template_state()
        if scene.load_map_image(file_path):
            self.map_status_label.setText(f"当前地图：{Path(file_path).name}")
            self.map_view.fit_scene()
            self.current_project_path = ""
            self.current_map_asset_path = ""
            self.current_map_floor_key = ""
            self._current_map_asset = None
            self._clear_overview_asset()
            self._rebuild_floor_panel()
            self._update_view_mode_availability()
            self._apply_timeline_column(self.current_keyframe_index)
            self._reset_history(mark_clean=True)
            return

        self.current_project_path = previous_project_path
        self._restore_history_state(before)

    def load_map_from_path(self, file_path: str) -> None:
        self._load_map_asset_with_history(file_path)

    def _load_map_asset_with_history(self, map_asset_path: str) -> bool:
        before = self._capture_history_state()
        previous_project_path = self.current_project_path
        self._pause_column_playback()
        self._reset_template_state()
        if not self._load_map_asset(map_asset_path):
            self.current_project_path = previous_project_path
            self._restore_history_state(before)
            return False
        self.current_project_path = ""
        self._apply_timeline_column(self.current_keyframe_index)
        self._reset_history(mark_clean=True)
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

        selection = self.session_service.load_map_selection(map_asset_path, floor_key)
        if selection is None:
            return False
        asset = selection.asset
        selected_floor = selection.floor
        if not scene.load_map_image(selected_floor.image_path):
            return False
        self._apply_operator_scale_to_views()

        previous_asset_path = self._current_map_asset.path if self._current_map_asset is not None else ""
        if not self._sync_overview_asset(asset, reset_camera=previous_asset_path != asset.path):
            return False

        if pause_playback:
            self._pause_column_playback()
        self.current_map_asset_path = asset.path
        self.current_map_floor_key = selected_floor.key
        self._current_map_asset = asset
        if previous_asset_path != asset.path or not self._overview_visible_floor_keys:
            self._overview_visible_floor_keys = {floor.key for floor in asset.floors}
        self.map_status_label.setText(f"当前地图：{asset.name} / {selected_floor.name}")
        self._update_view_mode_availability()
        self._rebuild_floor_panel()
        self._apply_overview_floor_visibility()
        self._sync_scene_surface_overlays()
        if fit_view:
            self._reset_active_view()
        self._refresh_property_panel()
        return True

    def _switch_map_floor(self, floor_key: str) -> None:
        if not self.current_map_asset_path or floor_key == self.current_map_floor_key:
            return
        if self._load_map_asset(self.current_map_asset_path, floor_key=floor_key, fit_view=False):
            self._apply_timeline_column(self.current_keyframe_index)

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

        project = self.session_service.load_project(file_path)
        self._apply_project(project)
        self.current_project_path = file_path
        self._reset_history(mark_clean=True)

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
        file_path = self.session_service.save_project(file_path, self._build_project(file_path))
        self.current_project_path = file_path
        self._mark_clean()
        return True

    def _add_operator(self) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        before = self._capture_history_state()
        self._pause_column_playback()
        operator = scene.add_operator(self._default_operator_position())
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
        operator = scene.add_operator(self._default_operator_position())
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
            self.show_icon_box.setChecked(True)
            self.show_name_box.setChecked(False)
            self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
            self.operator_size_value_label.setText(f"{int(round(self._operator_scale * 100))}%")
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
            show_icon = operator.show_icon if operator is not None else (
                target_frame.show_icon if target_frame is not None else True
            )
            show_name = operator.show_name if operator is not None else (
                target_frame.show_name if target_frame is not None else False
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
            self.show_icon_box.setChecked(show_icon)
            self.show_name_box.setChecked(show_name)
            self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
            self.operator_size_value_label.setText(f"{int(round(self._operator_scale * 100))}%")
            self.floor_value_label.setText(floor_key or self._current_floor_key())
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
        asset = self._current_map_asset
        if asset is None or len(asset.floors) <= 1:
            self.floor_panel.hide()
            return
        ordered_floors = list(reversed(asset.floors))

        if self._is_overview_mode():
            self.floor_panel.set_floors(
                ordered_floors,
                self.current_map_floor_key,
                self._toggle_overview_floor_visibility,
                multi_select=True,
                selected_floor_keys=self._overview_visible_floor_keys,
            )
        else:
            self.floor_panel.set_floors(
                ordered_floors,
                self.current_map_floor_key,
                self._switch_map_floor,
            )
        self._position_floor_panel()
        QTimer.singleShot(0, self._position_floor_panel)

    def _position_floor_panel(self) -> None:
        self.floor_panel.reposition(self._active_canvas_rect())

    def _position_playback_panel(self) -> None:
        self.playback_panel.reposition(self._active_canvas_rect())

    def _position_overlay_panels(self) -> None:
        self._position_floor_panel()
        self._position_playback_panel()

    def _set_property_enabled(self, enabled: bool) -> None:
        self.name_edit.setEnabled(enabled)
        self.side_combo.setEnabled(enabled)
        self.operator_combo.setEnabled(enabled)
        self.rotation_slider.setEnabled(enabled)
        self.show_icon_box.setEnabled(enabled)
        self.show_name_box.setEnabled(enabled)
        self.operator_size_slider.setEnabled(True)
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
        interactions = self._transition_interactions()
        if not interactions:
            return "当前地图没有可用互动点，手动路径将回退为自动。"
        interaction_ids = ", ".join(item.id for item in interactions[:6])
        if len(interactions) > 6:
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
        return self._route_planner().available_manual_interactions(
            start_state,
            end_state,
            default_floor_key=self._current_floor_key(),
        )

    def _manual_interaction_prefix(
        self,
        start_floor: str,
        manual_interaction_ids: list[str],
    ) -> tuple[list[tuple[MapInteractionPoint, str]], str] | None:
        return self._route_planner().manual_interaction_prefix(start_floor, manual_interaction_ids)

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
        return self._route_planner().can_reach_floor(start_floor, end_floor)

    @staticmethod
    def _interaction_choice_label(interaction: MapInteractionPoint) -> str:
        kind_label = "楼梯" if interaction.kind == MapInteractionType.STAIRS else "Hatch"
        suffix = f" | {interaction.label}" if interaction.label else ""
        return f"{interaction.floor_key} | {kind_label} | {interaction.id}{suffix}"

    def _manual_interaction_summary(self, selected_ids: list[str]) -> str:
        if not selected_ids:
            return "自动路径"
        lookup = {
            item.id: self._interaction_choice_label(item)
            for item in self._transition_interactions()
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
            for interaction in self._transition_interactions()
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

    def _explicit_current_frame(self, operator_id: str) -> OperatorFrameState | None:
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return None
        frame = self.keyframe_columns[self.current_keyframe_index].get(operator_id)
        return deepcopy(frame) if frame is not None else None

    def _current_transition_frame(self, operator_id: str) -> OperatorFrameState | None:
        frame = self._resolved_frame_state(operator_id, self.current_keyframe_index)
        if frame is None:
            return None

        explicit_frame = self._explicit_current_frame(operator_id)
        definition = self.operator_definitions.get(operator_id)
        gadget_asset = None
        ability_entry = None
        if definition is not None:
            if definition.gadget_key:
                gadget_asset = self.session_service.find_operator_gadget_asset(
                    definition.side.value,
                    definition.operator_key,
                    definition.gadget_key,
                )
            if definition.operator_key:
                ability_entry = self.session_service.find_operator_catalog_entry(
                    definition.operator_key,
                    definition.side.value,
                )

        editable_frame = deepcopy(frame)
        if gadget_asset is not None and not gadget_asset.persists_on_map:
            editable_frame.gadget_positions = (
                [Point2D(x=item.x, y=item.y) for item in (explicit_frame.gadget_positions or [])]
                if explicit_frame is not None and explicit_frame.gadget_positions is not None
                else []
            )
        if ability_entry is not None and not ability_entry.ability_persists_on_map:
            editable_frame.ability_positions = (
                [Point2D(x=item.x, y=item.y) for item in (explicit_frame.ability_positions or [])]
                if explicit_frame is not None and explicit_frame.ability_positions is not None
                else []
            )
        return editable_frame

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
        current_definition = self.operator_definitions.get(operator_id)
        next_gadget_key = ""
        if current_definition is not None and current_definition.gadget_key:
            candidate = self.session_service.find_operator_gadget_asset(
                side,
                current_definition.operator_key,
                current_definition.gadget_key,
            )
            next_gadget_key = candidate.key if candidate is not None else ""
        self._apply_global_operator_metadata(operator_id, side=side, gadget_key=next_gadget_key)
        if not next_gadget_key:
            self._clear_operator_gadget_deployments(operator_id)
            self._placing_gadget = False
        if self.session_service.find_operator_catalog_entry(
            self.operator_definitions.get(operator_id).operator_key if operator_id in self.operator_definitions else "",
            side,
        ) is None:
            self._clear_operator_ability_deployments(operator_id)
            self._placing_ability = False
        self._refresh_operator_combo(side)
        self._refresh_gadget_combo(side, next_gadget_key)
        self._apply_timeline_column(self.current_keyframe_index)
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
        self._clear_operator_ability_deployments(operator_id)
        self._placing_ability = False
        self._refresh_property_panel()
        self._refresh_timeline()
        self._commit_history(before)

    def _update_selected_gadget_asset(self, index: int) -> None:
        if self._syncing_panel:
            return
        operator = self._current_operator()
        operator_id = operator.operator_id if operator is not None else self._target_operator_id()
        if operator_id is None:
            return
        definition = self.operator_definitions.get(operator_id)
        current_key = definition.gadget_key if definition is not None else ""
        gadget_key = self.gadget_combo.itemData(index) or ""
        if gadget_key == current_key:
            return
        before = self._capture_history_state()
        self._apply_global_operator_metadata(operator_id, gadget_key=gadget_key)
        self._clear_operator_gadget_deployments(operator_id)
        self._placing_gadget = False
        self._refresh_current_column_visuals(refresh_overview=False)
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
                        show_icon=True,
                        show_name=False,
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

    def _on_operator_size_slider_pressed(self) -> None:
        self._operator_size_history_snapshot = self._capture_history_state()

    def _on_operator_size_slider_released(self) -> None:
        if self._operator_size_history_snapshot is None:
            return
        self._commit_history(self._operator_size_history_snapshot)
        self._operator_size_history_snapshot = None

    def _update_show_icon(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        self._update_display_options(show_icon=checked)

    def _update_show_name(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        self._update_display_options(show_name=checked)

    def _update_display_options(
        self,
        *,
        show_icon: bool | None = None,
        show_name: bool | None = None,
    ) -> None:
        operator = self._current_operator()
        before = self._capture_history_state()
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
                        display_mode=OperatorDisplayMode.ICON,
                        show_icon=True,
                        show_name=False,
                        floor_key=self._current_floor_key(),
                    )
                else:
                    current_frame = deepcopy(current_frame)
            next_show_icon = current_frame.show_icon if show_icon is None else bool(show_icon)
            next_show_name = current_frame.show_name if show_name is None else bool(show_name)
            if not next_show_icon and not next_show_name:
                if show_icon is False:
                    next_show_name = True
                else:
                    next_show_icon = True
            if (
                current_frame.show_icon == next_show_icon
                and current_frame.show_name == next_show_name
            ):
                return
            current_frame.show_icon = next_show_icon
            current_frame.show_name = next_show_name
            current_frame.display_mode = (
                OperatorDisplayMode.CUSTOM_NAME
                if next_show_name and not next_show_icon
                else OperatorDisplayMode.ICON
            )
            current_frame.floor_key = self._current_floor_key()
            self.keyframe_columns[self.current_keyframe_index][operator_id] = current_frame
            self._refresh_property_panel()
            self._refresh_timeline()
            self._commit_history(before)
            return

        next_show_icon = operator.show_icon if show_icon is None else bool(show_icon)
        next_show_name = operator.show_name if show_name is None else bool(show_name)
        if not next_show_icon and not next_show_name:
            if show_icon is False:
                next_show_name = True
            else:
                next_show_icon = True
        if operator.show_icon == next_show_icon and operator.show_name == next_show_name:
            return
        operator.set_display_options(next_show_icon, next_show_name)
        self._capture_selected_operator_to_current_cell(refresh_history=False)
        self._refresh_property_panel()
        self._commit_history(before)

    def _update_operator_scale(self, value: int) -> None:
        scale = max(0.5, min(1.6, value / 100.0))
        self.operator_size_value_label.setText(f"{value}%")
        if abs(self._operator_scale - scale) < 1e-6:
            return
        self._operator_scale = scale
        self._apply_operator_scale_to_views()
        self._refresh_property_panel()
        self._refresh_timeline()

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
                    show_icon=True,
                    show_name=False,
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
            for item in self._transition_interactions()
        }
        normalized_ids = [item for item in manual_ids if item in available_ids]
        frame = self._current_transition_frame(operator_id)
        if frame is None:
            frame = OperatorFrameState(
                id=operator_id,
                position=Point2D(x=0, y=0),
                rotation=0,
                display_mode=OperatorDisplayMode.ICON,
                show_icon=True,
                show_name=False,
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
            for interaction in self._transition_interactions()
        }
        manual_ids = [item for item in raw_ids if item in available_ids]

        frame = self._current_transition_frame(operator_id)
        if frame is None:
            frame = OperatorFrameState(
                id=operator_id,
                position=Point2D(x=0, y=0),
                rotation=0,
                display_mode=OperatorDisplayMode.ICON,
                show_icon=True,
                show_name=False,
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
        (
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
        ) = TimelineEditorController.add_keyframe_column(
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
        )
        self._refresh_timeline()
        self._commit_history(before)

    def _insert_keyframe_column(self) -> None:
        before = self._capture_history_state()
        self._pause_column_playback()
        (
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
        ) = TimelineEditorController.insert_keyframe_column(
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
        )
        self._refresh_timeline()
        self._commit_history(before)

    def _duplicate_keyframe_column(self) -> None:
        self._pause_column_playback()
        if not self.keyframe_columns:
            return
        before = self._capture_history_state()
        (
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
        ) = TimelineEditorController.duplicate_keyframe_column(
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
        )
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
            (
                self.keyframe_columns,
                self.keyframe_names,
                self.keyframe_notes,
                self.current_keyframe_index,
                self.current_timeline_row,
            ) = TimelineEditorController.delete_keyframe_column(
                self.keyframe_columns,
                self.keyframe_names,
                self.keyframe_notes,
                self.current_keyframe_index,
                column_index,
            )
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

        (
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
            _,
        ) = TimelineEditorController.delete_keyframe_column(
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
            column_index,
        )
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
        self.keyframe_columns = TimelineEditorController.set_cell(
            self.keyframe_columns,
            self.current_keyframe_index,
            operator.operator_id,
            state,
        )
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
                self.keyframe_columns = TimelineEditorController.set_cell(
                    self.keyframe_columns,
                    self.current_keyframe_index,
                    operator.operator_id,
                    state,
                )
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
        self.keyframe_columns = TimelineEditorController.clear_cell(
            self.keyframe_columns,
            column,
            operator_id,
        )
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
            self._activate_property_section("operator", context=("operator", operator_id), force=True)
            scene = self._map_scene()
            operator = scene.find_operator(operator_id) if scene is not None else None
            if operator is not None:
                scene.select_operator(operator)

        self._refresh_property_panel()
        self._refresh_timeline()

    def _select_keyframe_column(self, column: int) -> None:
        if not (0 <= column < len(self.keyframe_columns)):
            return
        scene = self._map_scene()
        if scene is not None:
            scene.clearSelection()
        self.current_timeline_row = -1
        self.current_surface_id = ""
        self.current_keyframe_index = column
        self._pause_column_playback()
        self._apply_column_with_focus_floor(self.current_keyframe_index)
        self._activate_property_section("keyframe", context=("keyframe", str(column)), force=True)
        self._refresh_property_panel()
        self._refresh_timeline()

    def _apply_timeline_column(self, column: int) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        self._applying_timeline = True
        resolved_current_floor = self._resolved_states(column)
        scene.sync_operator_states(resolved_current_floor)
        for operator in scene.operator_items():
            self._update_operator_icon(operator)
        self._sync_scene_surface_overlays()
        self._sync_overview_scene_states(self._resolved_states(column, include_all_floors=True))

        self._sync_operator_registry()
        self._refresh_property_panel()
        self._applying_timeline = False
        self._refresh_timeline()

    def _refresh_current_column_visuals(
        self,
        *,
        refresh_overview: bool = True,
        refresh_timeline: bool = True,
        refresh_property: bool = True,
    ) -> None:
        scene = self._map_scene()
        if scene is None:
            return

        self._applying_timeline = True
        resolved_current_floor = self._resolved_states(self.current_keyframe_index)
        scene.sync_operator_states(resolved_current_floor)
        for operator in scene.operator_items():
            self._update_operator_icon(operator)
        self._sync_scene_surface_overlays()
        if refresh_overview:
            self._sync_overview_scene_states(
                self._resolved_states(self.current_keyframe_index, include_all_floors=True)
            )
        self._sync_operator_registry()
        if refresh_property:
            self._refresh_property_panel()
        self._applying_timeline = False
        if refresh_timeline:
            self._refresh_timeline()

    def _resolved_frame_state(self, operator_id: str, column: int) -> OperatorFrameState | None:
        resolved: OperatorFrameState | None = None
        for current in range(0, column + 1):
            state = self.keyframe_columns[current].get(operator_id)
            if state is not None:
                state = deepcopy(state)
                if resolved is None:
                    if state.gadget_positions is None:
                        state.gadget_positions = []
                    if state.ability_positions is None:
                        state.ability_positions = []
                    if state.gadget_used_count is None:
                        state.gadget_used_count = len(state.gadget_positions)
                    if state.ability_used_count is None:
                        state.ability_used_count = len(state.ability_positions)
                    resolved = state
                    continue
                if state.gadget_used_count is None:
                    state.gadget_used_count = resolved.gadget_used_count
                if state.ability_used_count is None:
                    state.ability_used_count = resolved.ability_used_count
                if state.gadget_positions is None:
                    state.gadget_positions = [Point2D(x=item.x, y=item.y) for item in (resolved.gadget_positions or [])]
                if state.ability_positions is None:
                    state.ability_positions = [Point2D(x=item.x, y=item.y) for item in (resolved.ability_positions or [])]
                resolved = state
        return resolved

    def _resolved_state(self, operator_id: str, column: int) -> OperatorState | None:
        definition = self.operator_definitions.get(operator_id)
        frame = self._resolved_frame_state(operator_id, column)
        if definition is None or frame is None:
            return None
        state = resolve_operator_state(definition, frame)
        ability_entry = self._current_ability_entry(operator_id)
        gadget_asset = None
        if definition.gadget_key:
            gadget_asset = self.session_service.find_operator_gadget_asset(
                definition.side.value,
                definition.operator_key,
                definition.gadget_key,
            )
        if gadget_asset is not None and not gadget_asset.persists_on_map:
            explicit_frame = None
            if 0 <= column < len(self.keyframe_columns):
                explicit_frame = self.keyframe_columns[column].get(operator_id)
            state.gadget_positions = [
                Point2D(x=item.x, y=item.y)
                for item in ((explicit_frame.gadget_positions or []) if explicit_frame is not None else [])
            ]
        if ability_entry is not None and not ability_entry.ability_persists_on_map:
            explicit_frame = None
            if 0 <= column < len(self.keyframe_columns):
                explicit_frame = self.keyframe_columns[column].get(operator_id)
            state.ability_positions = [
                Point2D(x=item.x, y=item.y)
                for item in ((explicit_frame.ability_positions or []) if explicit_frame is not None else [])
            ]
        return state

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
        self.undo_button.setEnabled(self._history.can_undo())
        self.redo_button.setEnabled(self._history.can_redo())
        self._update_dirty_state()

    def _refresh_playback_panel(self) -> None:
        max_steps = max(len(self.keyframe_columns) - 1, 0)
        self.playback_progress_slider.blockSignals(True)
        self.playback_progress_slider.setRange(0, max_steps * 1000)
        if self._scrubbing_playback_slider:
            progress_value = self.playback_progress_slider.value()
        elif self._is_playing and self._playback_from_column >= 0 and self._playback_to_column >= 0:
            segment_progress = min(
                self._playback_elapsed_ms / max(self._current_playback_duration_ms(), 1),
                1.0,
            )
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
        if self._placing_gadget or self._placing_ability:
            self._refresh_property_panel()
            self._refresh_timeline()
            return
        scene = self._map_scene()
        operator = self._current_operator()
        surface = self._current_surface()
        if operator is None and surface is None and scene is not None and scene.selectedItems():
            return
        # Keep the timeline cell as the source of truth for placement mode.
        # Scene selection can temporarily disappear when switching floors because
        # the operator may not exist on the currently visible floor.
        if operator is not None:
            self.current_timeline_row = self._operator_row(operator.operator_id)
            self.current_surface_id = ""
            self._activate_property_section(
                "operator",
                context=("operator", operator.operator_id),
            )
        elif surface is not None:
            self.current_surface_id = surface.surface.id
            self._activate_property_section(
                "surface",
                context=("surface", surface.surface.id),
            )
        self._refresh_property_panel()
        self._refresh_timeline()

    def _on_surface_selected(self, surface_id: str) -> None:
        self.current_surface_id = surface_id
        self._activate_property_section("surface", context=("surface", surface_id), force=True)

    def _on_property_section_changed(self, index: int) -> None:
        section = {
            0: "operator",
            1: "surface",
            2: "keyframe",
        }.get(index, "operator")
        self.property_panel._active_section = section
        if self._syncing_property_section:
            return
        self._preferred_property_section = section

    def _activate_property_section(
        self,
        section: str,
        *,
        context: tuple[str, str] | None = None,
        force: bool = False,
    ) -> None:
        if not force and context is not None and self._last_property_auto_context == context:
            return
        if context is not None:
            self._last_property_auto_context = context
        if self.property_panel.active_section() == section:
            return
        self._syncing_property_section = True
        try:
            self.property_panel.set_active_section(section)
        finally:
            self._syncing_property_section = False

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

    def _on_gadget_transform_started(self) -> None:
        if self._applying_timeline:
            return
        self._pause_column_playback()
        self._gadget_transform_history_snapshot = self._capture_history_state()

    def _on_gadget_move_finished(
        self,
        operator_id: str,
        gadget_key: str,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        deleted: bool,
    ) -> None:
        before = self._gadget_transform_history_snapshot or self._capture_history_state()
        self._gadget_transform_history_snapshot = None
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return

        frame = self._current_transition_frame(operator_id)
        if frame is None:
            return

        updated_positions: list[Point2D] = []
        replaced = False
        for point in (frame.gadget_positions or []):
            if (
                not replaced
                and abs(point.x - from_x) < 0.1
                and abs(point.y - from_y) < 0.1
            ):
                replaced = True
                if not deleted:
                    updated_positions.append(Point2D(x=to_x, y=to_y))
                continue
            updated_positions.append(Point2D(x=point.x, y=point.y))

        if not replaced:
            if deleted:
                updated_positions = [
                    Point2D(x=point.x, y=point.y)
                    for point in (frame.gadget_positions or [])
                    if abs(point.x - to_x) >= 0.1 or abs(point.y - to_y) >= 0.1
                ]
            else:
                updated_positions.append(Point2D(x=to_x, y=to_y))

        new_frame = deepcopy(frame)
        new_frame.gadget_positions = updated_positions
        self.keyframe_columns[self.current_keyframe_index][operator_id] = new_frame
        self.current_timeline_row = self._operator_row(operator_id)
        self._apply_timeline_column(self.current_keyframe_index)
        self._commit_history(before)

    def _on_ability_transform_started(self) -> None:
        if self._applying_timeline:
            return
        self._pause_column_playback()
        self._gadget_transform_history_snapshot = self._capture_history_state()

    def _on_ability_move_finished(
        self,
        operator_id: str,
        ability_key: str,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        deleted: bool,
    ) -> None:
        before = self._gadget_transform_history_snapshot or self._capture_history_state()
        self._gadget_transform_history_snapshot = None
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return

        frame = self._current_transition_frame(operator_id)
        if frame is None:
            return

        updated_positions: list[Point2D] = []
        replaced = False
        for point in (frame.ability_positions or []):
            if (
                not replaced
                and abs(point.x - from_x) < 0.1
                and abs(point.y - from_y) < 0.1
            ):
                replaced = True
                if not deleted:
                    updated_positions.append(Point2D(x=to_x, y=to_y))
                continue
            updated_positions.append(Point2D(x=point.x, y=point.y))

        if not replaced:
            if deleted:
                updated_positions = [
                    Point2D(x=point.x, y=point.y)
                    for point in (frame.ability_positions or [])
                    if abs(point.x - to_x) >= 0.1 or abs(point.y - to_y) >= 0.1
                ]
            else:
                updated_positions.append(Point2D(x=to_x, y=to_y))

        new_frame = deepcopy(frame)
        new_frame.ability_positions = updated_positions
        self.keyframe_columns[self.current_keyframe_index][operator_id] = new_frame
        self.current_timeline_row = self._operator_row(operator_id)
        self._apply_timeline_column(self.current_keyframe_index)
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
        self._playback_effective_duration_ms = float(self._transition_duration_ms)
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
        progress = min(self._playback_elapsed_ms / max(self._current_playback_duration_ms(), 1), 1.0)
        self._sync_playback_focus_floor(progress)
        scene.sync_operator_states(self._interpolated_states(progress))
        for operator in scene.operator_items():
            self._update_operator_icon(operator)
        self._sync_overview_scene_states(
            self._interpolated_states(progress, include_all_floors=True)
        )
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
        self._playback_effective_duration_ms = self._effective_playback_duration_ms(self._playback_routes)
        self.playback_timer.start()

    def _sync_playback_focus_floor(self, progress: float) -> None:
        if self._is_overview_mode():
            return
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
        if self._is_overview_mode():
            return
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

    def _interpolated_states(
        self,
        progress: float,
        *,
        include_all_floors: bool = False,
    ) -> list[OperatorState]:
        states: list[OperatorState] = []
        for operator_id in self.operator_order:
            state = self._interpolated_state_for_operator(operator_id, progress)
            if state is None:
                continue
            if not include_all_floors and not self._state_matches_current_floor(state):
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
        if self._is_overview_mode() and self._is_playing:
            route_state = self._overview_state_on_route(start_state, end_state, route, progress)
        else:
            route_state = self._state_on_route(start_state, end_state, route, progress)
        if route_state is None:
            return None

        rotation_delta = ((end_state.rotation - start_state.rotation + 180) % 360) - 180
        route_state.rotation = start_state.rotation + rotation_delta * progress
        route_state.display_mode = end_state.display_mode
        route_state.show_icon = end_state.show_icon
        route_state.show_name = end_state.show_name
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
        return self._route_planner().build_transition_route(
            start_state,
            end_state,
            default_floor_key=self._current_floor_key(),
            transition_mode=transition_mode,
            manual_interaction_ids=manual_interaction_ids or [],
        )

    def _transition_settings_for_operator(
        self,
        operator_id: str,
        from_column: int,
    ) -> tuple[OperatorTransitionMode, list[str]]:
        frame = self._resolved_frame_state(operator_id, from_column)
        if frame is None:
            return (OperatorTransitionMode.AUTO, [])
        return (frame.transition_mode, list(frame.manual_interaction_ids))

    def _state_on_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list[PlaybackRouteSegment],
        progress: float,
    ) -> OperatorState:
        return self._route_planner().state_on_route(
            start_state,
            end_state,
            route,
            progress,
            default_floor_key=self._current_floor_key(),
        )

    def _current_playback_duration_ms(self) -> float:
        if self._is_playing and self._playback_to_column >= 0:
            return self._playback_effective_duration_ms
        return float(self._transition_duration_ms)

    def _effective_playback_duration_ms(
        self,
        routes: dict[str, list[PlaybackRouteSegment]],
    ) -> float:
        base = float(self._transition_duration_ms)
        if not self._is_overview_mode():
            return base
        max_floor_changes = max(
            (
                self._route_floor_change_count(route)
                for route in routes.values()
            ),
            default=0,
        )
        return base + max_floor_changes * self._overview_extra_vertical_duration_ms()

    def _overview_extra_vertical_duration_ms(self) -> float:
        return float(self._transition_duration_ms) * 0.5

    @staticmethod
    def _route_floor_change_count(route: list[PlaybackRouteSegment]) -> int:
        return sum(
            1
            for segment in route
            if segment.result_floor_key and segment.result_floor_key != segment.floor_key
        )

    def _route_total_duration_ms(self, route: list[PlaybackRouteSegment]) -> float:
        return float(self._transition_duration_ms) + sum(
            self._transition_duration_for_segment(route, segment)
            for segment in route
            if segment.result_floor_key and segment.result_floor_key != segment.floor_key
        )

    def _transition_duration_for_segment(
        self,
        route: list[PlaybackRouteSegment],
        segment: PlaybackRouteSegment,
    ) -> float:
        if not segment.result_floor_key or segment.result_floor_key == segment.floor_key:
            return 0.0

        extra_total = self._route_floor_change_count(route) * self._overview_extra_vertical_duration_ms()
        if extra_total <= 0.0:
            return 0.0

        weighted_segments = [
            candidate
            for candidate in route
            if candidate.result_floor_key and candidate.result_floor_key != candidate.floor_key
        ]
        if not weighted_segments:
            return 0.0

        total_weight = sum(max(self._transition_segment_weight(candidate), 1.0) for candidate in weighted_segments)
        if total_weight <= 0.001:
            return extra_total / len(weighted_segments)
        return extra_total * (max(self._transition_segment_weight(segment), 1.0) / total_weight)

    def _transition_segment_weight(self, segment: PlaybackRouteSegment) -> float:
        planner = self._route_planner()
        length = planner.transition_path_length(segment)
        if length > 0.001:
            return length
        return 1.0

    def _route_phase_at_elapsed(
        self,
        route: list[PlaybackRouteSegment],
        elapsed_ms: float,
    ) -> tuple[str, PlaybackRouteSegment | None, float]:
        if not route:
            return ("final", None, 1.0)

        base_duration = float(self._transition_duration_ms)
        total_horizontal = sum(self._route_planner().route_segment_length(segment) for segment in route)
        horizontal_fallback_ms = base_duration / max(len(route), 1)
        consumed = 0.0

        for index, segment in enumerate(route):
            segment_length = self._route_planner().route_segment_length(segment)
            horizontal_ms = (
                base_duration * (segment_length / total_horizontal)
                if total_horizontal > 0.001
                else horizontal_fallback_ms
            )

            if elapsed_ms <= consumed + horizontal_ms or (
                index == len(route) - 1
                and elapsed_ms < self._route_total_duration_ms(route)
                and horizontal_ms <= 0.0
            ):
                local_progress = (
                    max(0.0, min(1.0, (elapsed_ms - consumed) / horizontal_ms))
                    if horizontal_ms > 0.0
                    else 1.0
                )
                return ("horizontal", segment, local_progress)
            consumed += horizontal_ms

            if segment.result_floor_key and segment.result_floor_key != segment.floor_key:
                extra_vertical_ms = self._transition_duration_for_segment(route, segment)
                if elapsed_ms <= consumed + extra_vertical_ms:
                    local_progress = (
                        max(0.0, min(1.0, (elapsed_ms - consumed) / extra_vertical_ms))
                        if extra_vertical_ms > 0.0
                        else 1.0
                    )
                    return ("vertical", segment, local_progress)
                consumed += extra_vertical_ms

        return ("final", route[-1], 1.0)

    def _overview_state_on_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list[PlaybackRouteSegment],
        progress: float,
    ) -> OperatorState:
        if not route:
            return deepcopy(end_state)

        elapsed_ms = self._current_playback_duration_ms() * progress
        phase, segment, local_progress = self._route_phase_at_elapsed(route, elapsed_ms)
        if segment is None or phase == "final":
            return deepcopy(end_state)

        if phase == "horizontal":
            position = Point2D(
                x=segment.start.x + (segment.end.x - segment.start.x) * local_progress,
                y=segment.start.y + (segment.end.y - segment.start.y) * local_progress,
            )
            return self._route_planner().copy_state_with_position(end_state, position, segment.floor_key)

        planner = self._route_planner()
        transition_position = planner.transition_point_at_progress(segment, local_progress)
        floor_key = (
            segment.floor_key
            if local_progress < 0.5 or not segment.result_floor_key
            else segment.result_floor_key
        )
        return planner.copy_state_with_position(end_state, transition_position, floor_key)

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
        self.keyframe_names = TimelineEditorController.update_keyframe_name(
            self.keyframe_names,
            self.current_keyframe_index,
            name,
        )
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
        self.keyframe_notes = TimelineEditorController.update_keyframe_note(
            self.keyframe_notes,
            self.current_keyframe_index,
            note,
        )
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
        (
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
        ) = TimelineEditorController.move_keyframe_column(
            self.keyframe_columns,
            self.keyframe_names,
            self.keyframe_notes,
            self.current_keyframe_index,
            from_index,
            to_index,
        )
        self._apply_timeline_column(self.current_keyframe_index)
        self._refresh_timeline()
        self._commit_history(before)

    def _move_operator_row(self, from_index: int, to_index: int) -> None:
        if not (0 <= from_index < len(self.operator_order) and 0 <= to_index < len(self.operator_order)):
            return
        if from_index == to_index:
            return
        before = self._capture_history_state()
        self.operator_order, self.current_timeline_row = TimelineEditorController.move_operator_row(
            self.operator_order,
            self.current_timeline_row,
            from_index,
            to_index,
        )
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
        token_mode_active = self._placing_gadget or self._placing_ability
        scene.set_placement_state(None if token_mode_active else self._current_placement_state())
        gadget_asset = self._current_gadget_asset()
        gadget_positions = self._current_gadget_positions()
        scene.set_gadget_placement(
            operator_id=self._target_operator_id() or "",
            gadget_key=gadget_asset.key if gadget_asset is not None else "",
            icon_path=gadget_asset.path if gadget_asset is not None else "",
            max_count=gadget_asset.max_count if gadget_asset is not None else 0,
            active=self._placing_gadget and gadget_asset is not None,
            positions=gadget_positions,
        )
        ability_entry = self._current_ability_entry()
        ability_positions = self._current_ability_positions()
        scene.set_ability_placement(
            operator_id=self._target_operator_id() or "",
            ability_key=ability_entry.key if ability_entry is not None else "",
            icon_path=ability_entry.ability_icon_path if ability_entry is not None else "",
            active=self._placing_ability and ability_entry is not None and bool(ability_entry.ability_icon_path),
            positions=ability_positions,
        )

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
        overview_scene = self._overview_scene()
        if overview_scene is not None:
            overview_scene.set_preview_routes(self._current_preview_routes())

    def _sync_scene_surface_overlays(self) -> None:
        scene = self._map_scene()
        if scene is None:
            return
        surfaces = self._current_map_asset.surfaces if self._current_map_asset is not None else []
        scene.set_surface_overlays(surfaces, self.surface_states, self._current_floor_key())
        if self.current_surface_id:
            scene.select_surface(self.current_surface_id)

    def _current_preview_routes(self) -> dict[str, list[PlaybackRouteSegment]]:
        routes: dict[str, list[PlaybackRouteSegment]] = {}
        if self._is_playing and self._playback_from_column >= 0 and self._playback_to_column >= 0:
            from_column = self._playback_from_column
            to_column = self._playback_to_column
        else:
            from_column = self.current_keyframe_index
            to_column = self.current_keyframe_index + 1

        if to_column >= len(self.keyframe_columns):
            return {}

        for operator_id in self.operator_order:
            start_state = self._resolved_state(operator_id, from_column)
            end_state = self._resolved_state(operator_id, to_column)
            if start_state is None or end_state is None:
                continue
            route = self._build_transition_route_for_operator(
                operator_id,
                start_state,
                end_state,
                from_column,
            )
            if route:
                routes[operator_id] = route
        return routes

    def _current_preview_segments(self) -> dict[str, tuple[OperatorState, OperatorState]]:
        if self._is_playing and self._playback_from_column >= 0 and self._playback_to_column >= 0:
            progress = min(self._playback_elapsed_ms / max(self._current_playback_duration_ms(), 1), 1.0)
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
        return self._route_planner().preview_segment_on_route(
            start_state,
            end_state,
            route,
            progress,
            current_floor_key=self._current_floor_key(),
        )

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
                    show_icon=True,
                    show_name=False,
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

    def _resolved_states(
        self,
        column: int,
        *,
        include_all_floors: bool = False,
    ) -> list[OperatorState]:
        resolved_states: list[OperatorState] = []
        for operator_id in self.operator_order:
            state = self._resolved_state(operator_id, column)
            if state is None:
                continue
            if not include_all_floors and not self._state_matches_current_floor(state):
                continue
            resolved_states.append(deepcopy(state))
        return resolved_states

    def _operator_label(self, operator_id: str) -> str:
        definition = self.operator_definitions.get(operator_id)
        if definition is None or not definition.custom_name:
            return f"干员 {operator_id}"
        return definition.custom_name

    def _target_operator_id(self) -> str | None:
        if 0 <= self.current_timeline_row < len(self.operator_order):
            return self.operator_order[self.current_timeline_row]
        return None

    def _selected_surface_asset(self) -> MapSurface | None:
        if self._current_map_asset is None or not self.current_surface_id:
            return None
        for surface in self._current_map_asset.surfaces:
            if surface.id == self.current_surface_id:
                return surface
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
        assets = self.session_service.list_operator_assets(side)
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

    def _refresh_gadget_combo(self, side: str, selected_key: str = "") -> None:
        operator_id = self._target_operator_id()
        definition = self.operator_definitions.get(operator_id) if operator_id is not None else None
        if definition is not None and definition.operator_key:
            assets = self.session_service.list_operator_gadget_assets(side, definition.operator_key)
        else:
            assets = self.session_service.list_gadget_assets(side)
        self.gadget_combo.blockSignals(True)
        self.gadget_combo.clear()
        self.gadget_combo.addItem("(未指定)")
        self.gadget_combo.setItemData(0, "")

        current_index = 0
        for index, asset in enumerate(assets, start=1):
            self.gadget_combo.addItem(asset.name)
            self.gadget_combo.setItemData(index, asset.key)
            if asset.key == selected_key:
                current_index = index

        self.gadget_combo.setCurrentIndex(current_index)
        self.gadget_combo.blockSignals(False)

    def _update_operator_icon(self, operator: OperatorItem) -> None:
        asset = self.session_service.find_operator_asset(operator.side, operator.operator_key)
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
                    gadget_key=(
                        self.operator_definitions[operator.operator_id].gadget_key
                        if operator.operator_id in self.operator_definitions
                        else ""
                    ),
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

    def _sync_gadget_catalog(self) -> None:
        scene = self._map_scene()
        if scene is None:
            return
        catalog: dict[tuple[str, str], str] = {}
        for side in ("attack", "defense"):
            for asset in self.session_service.list_gadget_assets(side):
                catalog[(asset.side, asset.key)] = asset.path
        scene.set_gadget_catalog(catalog)
        ability_catalog: dict[tuple[str, str], str] = {}
        for side in ("attack", "defense"):
            for entry in self.session_service.list_operator_catalog(side):
                if entry.ability_icon_path:
                    ability_catalog[(entry.side, entry.key)] = entry.ability_icon_path
        scene.set_ability_catalog(ability_catalog)

    def _remove_operator_from_timeline(self, operator_id: str) -> None:
        self.keyframe_columns, self.operator_definitions = TimelineEditorController.remove_operator_from_timeline(
            self.keyframe_columns,
            self.operator_definitions,
            operator_id,
        )

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
            OperatorDisplayMode.CUSTOM_NAME
            if operator.show_name and not operator.show_icon
            else OperatorDisplayMode.ICON
        )
        current_frame = self._current_transition_frame(operator.operator_id)
        return OperatorFrameState(
            id=operator.operator_id,
            position=Point2D(x=operator.pos().x(), y=operator.pos().y()),
            rotation=operator.rotation(),
            display_mode=display_mode,
            show_icon=operator.show_icon,
            show_name=operator.show_name,
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
            gadget_positions=(
                [Point2D(x=item.x, y=item.y) for item in (current_frame.gadget_positions or [])]
                if current_frame is not None
                else None
            ),
            ability_positions=(
                [Point2D(x=item.x, y=item.y) for item in (current_frame.ability_positions or [])]
                if current_frame is not None
                else None
            ),
        )

    def _apply_global_operator_metadata(
        self,
        operator_id: str,
        *,
        custom_name: str | None = None,
        side: str | None = None,
        operator_key: str | None = None,
        gadget_key: str | None = None,
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
                gadget_key="",
            )

        if custom_name is not None:
            definition.custom_name = custom_name
        if side is not None:
            definition.side = TeamSide(side)
        if operator_key is not None:
            definition.operator_key = operator_key
        if gadget_key is not None:
            definition.gadget_key = gadget_key

        self.operator_definitions[operator_id] = definition

        if operator is not None:
            operator.set_custom_name(definition.custom_name)
            operator.set_side(definition.side.value)
            operator.set_operator_key(definition.operator_key)
            self._update_operator_icon(operator)

    def _build_project(self, project_path: str = "") -> TacticProject:
        scene = self._map_scene()
        return self.session_service.build_project(
            project_path=project_path or self.current_project_path,
            current_map_asset=self._current_map_asset,
            current_map_asset_path=self.current_map_asset_path,
            current_map_floor_key=self.current_map_floor_key,
            map_image_path=scene.current_map_path if scene is not None else "",
            operator_order=self.operator_order,
            operator_definitions=self.operator_definitions,
            keyframe_columns=self.keyframe_columns,
            keyframe_names=self.keyframe_names,
            keyframe_notes=self.keyframe_notes,
            surface_states=self.surface_states,
            current_keyframe_index=self.current_keyframe_index,
            transition_duration_ms=self._transition_duration_ms,
            operator_scale=self._operator_scale,
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
                self._clear_overview_asset()
                self._rebuild_floor_panel()
        elif project.map_info and project.map_info.image_path:
            if scene.load_map_image(project.map_info.image_path):
                self.map_status_label.setText(f"当前地图：{Path(project.map_info.image_path).name}")
                self.map_view.fit_scene()
                self.current_map_asset_path = ""
                self.current_map_floor_key = ""
                self._current_map_asset = None
                self._clear_overview_asset()
                self._rebuild_floor_panel()
            else:
                self.map_status_label.setText("当前地图：加载失败")
        else:
            scene.clear_map()
            self.map_status_label.setText("当前地图：未加载")
            self.current_map_asset_path = ""
            self.current_map_floor_key = ""
            self._current_map_asset = None
            self._clear_overview_asset()
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
        self.surface_states = {
            state.surface_id: self._normalized_surface_state(state.surface_id, deepcopy(state))
            for state in project.surface_states
            if self._normalized_surface_state(state.surface_id, deepcopy(state)) != self._default_surface_state(state.surface_id)
        }
        self.current_keyframe_index = min(project.current_keyframe_index, len(self.keyframe_columns) - 1)
        self.current_timeline_row = -1
        self.current_surface_id = ""
        self._placing_gadget = False
        self._transition_duration_ms = project.transition_duration_ms
        self._operator_scale = project.operator_scale
        self.playback_duration_slider.setValue(self._transition_duration_ms)
        self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
        self._apply_operator_scale_to_views()
        self._update_view_mode_availability()

        for operator_id in self.operator_definitions:
            if operator_id not in self.operator_order:
                self.operator_order.append(operator_id)
        for frame in self.keyframe_columns:
            for state in frame.values():
                if state.id not in self.operator_order:
                    self.operator_order.append(state.id)

        self._apply_timeline_column(self.current_keyframe_index)
        self._refresh_timeline()

    def _reset_template_state(self) -> None:
        self.operator_order = []
        self.operator_definitions = {}
        self.keyframe_columns = [{}]
        self.keyframe_names = [""]
        self.keyframe_notes = [""]
        self.current_keyframe_index = 0
        self.current_timeline_row = -1
        self.current_surface_id = ""
        self._placing_gadget = False
        self._transition_duration_ms = 700
        self._operator_scale = 1.0
        self.playback_duration_slider.setValue(self._transition_duration_ms)
        self.operator_size_slider.setValue(100)
        self._apply_operator_scale_to_views()

    def _capture_project_state(self) -> EditorProjectState:
        scene = self._map_scene()
        map_reference_path = self.current_map_asset_path
        if not map_reference_path and scene is not None:
            map_reference_path = scene.current_map_path
        return EditorProjectState(
            map_reference_path=map_reference_path,
            operator_order=list(self.operator_order),
            operator_definitions=deepcopy(self.operator_definitions),
            keyframe_columns=deepcopy(self.keyframe_columns),
            keyframe_names=list(self.keyframe_names),
            keyframe_notes=list(self.keyframe_notes),
            surface_states=deepcopy(self.surface_states),
            transition_duration_ms=self._transition_duration_ms,
            operator_scale=self._operator_scale,
        )

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
            selected_surface_id=self.current_surface_id,
            surface_states=deepcopy(self.surface_states),
            transition_duration_ms=self._transition_duration_ms,
            operator_scale=self._operator_scale,
        )

    def _commit_history(self, before: EditorHistoryState) -> None:
        if self._history_lock:
            return
        after = self._capture_history_state()
        if self._history.commit(before, after):
            self._refresh_timeline()

    def _reset_history(self, *, mark_clean: bool = False) -> None:
        history_snapshot = self._capture_history_state()
        self._history.reset(history_snapshot)
        if mark_clean or self._clean_project_state is None:
            self._clean_project_state = self._capture_project_state()
        self._refresh_timeline()

    def _mark_clean(self) -> None:
        self._history.mark_clean(self._capture_history_state())
        self._clean_project_state = self._capture_project_state()
        self._update_dirty_state()

    def undo(self) -> None:
        current = self._capture_history_state()
        snapshot = self._history.undo(current)
        if snapshot is None:
            return
        self._restore_history_state(snapshot)

    def redo(self) -> None:
        current = self._capture_history_state()
        snapshot = self._history.redo(current)
        if snapshot is None:
            return
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
                self._clear_overview_asset()
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
            self._clear_overview_asset()
            self._rebuild_floor_panel()

        self.operator_order = list(snapshot.operator_order)
        self.operator_definitions = deepcopy(snapshot.operator_definitions)
        self.keyframe_columns = deepcopy(snapshot.keyframe_columns)
        self.keyframe_names = list(snapshot.keyframe_names)
        self.keyframe_notes = list(snapshot.keyframe_notes)
        self.current_keyframe_index = snapshot.current_keyframe_index
        self.current_timeline_row = snapshot.current_timeline_row
        self.current_surface_id = snapshot.selected_surface_id
        self.surface_states = deepcopy(snapshot.surface_states)
        self._transition_duration_ms = snapshot.transition_duration_ms
        self._operator_scale = snapshot.operator_scale
        self.playback_duration_slider.setValue(self._transition_duration_ms)
        self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
        self._apply_operator_scale_to_views()

        scene.sync_operator_states(deepcopy(snapshot.scene_states), snapshot.selected_operator_id or None)
        self._sync_scene_surface_overlays()
        for operator in scene.operator_items():
            self._update_operator_icon(operator)
        self._sync_overview_scene_states(
            self._resolved_states(self.current_keyframe_index, include_all_floors=True)
        )

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

    def _current_surface(self):
        scene = self._map_scene()
        if scene is None:
            return None
        return scene.selected_surface()

    def _map_scene(self) -> MapScene | None:
        scene = self.map_view.scene()
        if isinstance(scene, MapScene):
            return scene
        return None

    def _overview_scene(self) -> OverviewScene | None:
        return self.overview_view.overview_scene()

    def _sync_overview_asset(self, asset: MapAsset, *, reset_camera: bool) -> bool:
        return self.overview_view.set_map_asset(asset, reset_camera=reset_camera)

    def _clear_overview_asset(self) -> None:
        self._overview_visible_floor_keys = set()
        self.overview_view.clear_map()

    def _apply_operator_scale_to_views(self) -> None:
        scene = self._map_scene()
        if scene is not None:
            scene.set_operator_scale(self._operator_scale)
        self.overview_view.set_operator_scale(self._operator_scale)

    def _sync_overview_scene_states(self, states: list[OperatorState]) -> None:
        scene = self._overview_scene()
        if scene is None:
            return
        selected_operator_id = self._target_operator_id() or ""
        scene.sync_operator_states(states, selected_operator_id=selected_operator_id)
        scene.set_render_position_overrides(self._current_overview_position_overrides())
        self._apply_overview_floor_visibility()

    def _apply_overview_floor_visibility(self) -> None:
        scene = self._overview_scene()
        if scene is None:
            return
        scene.set_visible_floors(self._overview_visible_floor_keys)

    def _toggle_overview_floor_visibility(self, floor_key: str) -> None:
        if not self._current_map_asset:
            return
        if floor_key in self._overview_visible_floor_keys:
            if len(self._overview_visible_floor_keys) <= 1:
                return
            self._overview_visible_floor_keys.remove(floor_key)
        else:
            self._overview_visible_floor_keys.add(floor_key)
        self._rebuild_floor_panel()
        self._apply_overview_floor_visibility()
        self._sync_scene_preview_paths()

    def _current_overview_position_overrides(self) -> dict[str, tuple[float, float, float]]:
        if not self._is_overview_mode() or not self._is_playing:
            return {}
        scene = self._overview_scene()
        if scene is None:
            return {}

        overrides: dict[str, tuple[float, float, float]] = {}
        for operator_id in self.operator_order:
            start_state = self._playback_start_states.get(operator_id)
            end_state = self._playback_end_states.get(operator_id, start_state)
            if start_state is None or end_state is None:
                continue
            route = self._playback_routes.get(operator_id, [])
            world_position = self._overview_world_position_on_route(
                scene,
                start_state,
                end_state,
                route,
                self._playback_elapsed_ms,
            )
            if world_position is not None:
                overrides[operator_id] = world_position
        return overrides

    def _overview_world_position_on_route(
        self,
        scene: OverviewScene,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list[PlaybackRouteSegment],
        elapsed_ms: float,
    ) -> tuple[float, float, float] | None:
        if not route:
            return scene.world_point(
                end_state.floor_key or start_state.floor_key or self._current_floor_key(),
                end_state.position.x,
                end_state.position.y,
                z_offset=8.0,
            )

        phase, segment, local_progress = self._route_phase_at_elapsed(route, elapsed_ms)
        if segment is None or phase == "final":
            return scene.world_point(
                end_state.floor_key or self._current_floor_key(),
                end_state.position.x,
                end_state.position.y,
                z_offset=8.0,
            )

        if phase == "horizontal":
            x = segment.start.x + (segment.end.x - segment.start.x) * local_progress
            y = segment.start.y + (segment.end.y - segment.start.y) * local_progress
            return scene.world_point(segment.floor_key, x, y, z_offset=8.0)

        planner = self._route_planner()
        transition_points = segment.transition_points
        if segment.interaction_kind == MapInteractionType.STAIRS and len(transition_points) >= 2:
            point_progress = max(0.0, min(1.0, local_progress))
            transition_position = planner.transition_point_at_progress(segment, point_progress)
            start_world = scene.world_point(segment.floor_key, transition_points[0].x, transition_points[0].y, z_offset=8.0)
            end_anchor = segment.result_position or transition_points[-1]
            end_world = scene.world_point(
                segment.result_floor_key,
                end_anchor.x,
                end_anchor.y,
                z_offset=8.0,
            )
            if start_world is None or end_world is None:
                return None
            current_world = scene.world_point(segment.floor_key, transition_position.x, transition_position.y, z_offset=8.0)
            if current_world is None:
                return None
            z_progress = point_progress
            return (
                current_world[0],
                current_world[1],
                start_world[2] + (end_world[2] - start_world[2]) * z_progress,
            )

        start_world = scene.world_point(segment.floor_key, segment.end.x, segment.end.y, z_offset=8.0)
        result_position = segment.result_position or segment.end
        end_world = scene.world_point(
            segment.result_floor_key,
            result_position.x,
            result_position.y,
            z_offset=8.0,
        )
        if start_world is None or end_world is None:
            return None
        return (
            start_world[0] + (end_world[0] - start_world[0]) * local_progress,
            start_world[1] + (end_world[1] - start_world[1]) * local_progress,
            start_world[2] + (end_world[2] - start_world[2]) * local_progress,
        )

    def _default_operator_position(self) -> QPointF:
        if self._is_overview_mode():
            scene = self._map_scene()
            return scene.sceneRect().center() if scene is not None else QPointF()
        return self.map_view.scene_center()

    def _active_canvas_widget(self) -> QWidget:
        return self.overview_view if self._is_overview_mode() else self.map_view

    def _active_canvas_rect(self) -> QRect:
        widget = self._active_canvas_widget()
        top_left = widget.mapTo(self, QPoint(0, 0))
        return QRect(top_left, widget.size())

    def _is_overview_mode(self) -> bool:
        return self._view_mode == "overview_2p5d"

    def _reset_active_view(self) -> None:
        if self._is_overview_mode():
            self.overview_view.reset_view()
        else:
            self.map_view.reset_view()

    def _on_view_mode_changed(self, index: int) -> None:
        mode = self.view_mode_combo.itemData(index) or "single_floor"
        self._set_view_mode(str(mode))

    def _set_view_mode(self, mode: str) -> None:
        if mode == self._view_mode:
            self._position_overlay_panels()
            return
        if mode == "overview_2p5d" and not self._supports_overview_view():
            self.view_mode_combo.blockSignals(True)
            self.view_mode_combo.setCurrentIndex(0)
            self.view_mode_combo.blockSignals(False)
            mode = "single_floor"

        self._view_mode = mode
        self.canvas_stack.setCurrentWidget(self.overview_view if self._is_overview_mode() else self.map_view)
        self._rebuild_floor_panel()
        self._position_overlay_panels()
        if self._is_overview_mode():
            if not self._overview_visible_floor_keys and self._current_map_asset is not None:
                self._overview_visible_floor_keys = {floor.key for floor in self._current_map_asset.floors}
            self._sync_overview_scene_states(
                self._resolved_states(self.current_keyframe_index, include_all_floors=True)
            )
            self.overview_view.reset_view()
        else:
            self._apply_column_with_focus_floor(self.current_keyframe_index)

    def _supports_overview_view(self) -> bool:
        asset = self._current_map_asset
        if asset is None or len(asset.floors) <= 1:
            return False
        overview = asset.overview_2p5d
        return overview is None or overview.enabled

    def _update_view_mode_availability(self) -> None:
        supported = self._supports_overview_view()
        self.view_mode_combo.setEnabled(supported)
        if not supported and self._is_overview_mode():
            self.view_mode_combo.blockSignals(True)
            self.view_mode_combo.setCurrentIndex(0)
            self.view_mode_combo.blockSignals(False)
            self._set_view_mode("single_floor")

    def _route_planner(self) -> InteractionRoutePlanner:
        return InteractionRoutePlanner(self._transition_interactions())

    def _transition_interactions(self) -> list[MapInteractionPoint]:
        if self._current_map_asset is None:
            return []

        interactions = [
            deepcopy(item)
            for item in self._current_map_asset.interactions
            if item.kind == MapInteractionType.STAIRS
        ]
        interactions.extend(self._hatch_surface_interactions())
        return interactions

    def _hatch_surface_interactions(self) -> list[MapInteractionPoint]:
        if self._current_map_asset is None:
            return []

        hatch_interactions: list[MapInteractionPoint] = []
        for surface in self._current_map_asset.surfaces:
            if surface.kind != MapSurfaceType.HATCH:
                continue
            center = Point2D(
                x=(surface.start.x + surface.end.x) / 2,
                y=(surface.start.y + surface.end.y) / 2,
            )
            hatch_interactions.append(
                MapInteractionPoint(
                    id=surface.id,
                    kind=MapInteractionType.HATCH,
                    position=center,
                    floor_key=surface.floor_key,
                    linked_floor_keys=list(surface.linked_floor_keys),
                    is_bidirectional=surface.is_bidirectional,
                    label=surface.label,
                    note=surface.note,
                )
            )
        return hatch_interactions

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
        if self._clean_project_state is None:
            return False
        current = self._capture_project_state()
        return current != self._clean_project_state

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

    def _reset_template_state(self) -> None:
        self.operator_order = []
        self.operator_definitions = {}
        self.keyframe_columns = [{}]
        self.keyframe_names = [""]
        self.keyframe_notes = [""]
        self.surface_states = {}
        self.current_keyframe_index = 0
        self.current_timeline_row = -1
        self.current_surface_id = ""
        self._transition_duration_ms = 700
        self._operator_scale = 1.0
        self._placing_gadget = False
        self._placing_ability = False
        self.playback_duration_slider.setValue(self._transition_duration_ms)
        self.operator_size_slider.setValue(100)

    def _refresh_property_panel(self) -> None:
        if self.manual_interaction_combo.view().isVisible():
            self._schedule_property_panel_refresh()
            return

        operator = self._current_operator()
        target_operator_id = self._target_operator_id()
        target_definition = self.operator_definitions.get(target_operator_id) if target_operator_id is not None else None
        target_frame = (
            self._resolved_frame_state(target_operator_id, self.current_keyframe_index)
            if target_operator_id is not None and 0 <= self.current_keyframe_index < len(self.keyframe_columns)
            else None
        )
        selected_surface = self._selected_surface_asset()

        self._syncing_panel = True
        if operator is None and target_operator_id is None:
            self.selection_label.setText("当前选中：无")
            self.name_edit.setText("")
            self.side_combo.setCurrentIndex(0)
            self._refresh_operator_combo("attack")
            self._refresh_gadget_combo("attack")
            self.rotation_slider.setValue(0)
            self.rotation_value_label.setText("0°")
            self.gadget_count_label.setText("-")
            self.ability_name_label.setText("-")
            self.ability_count_label.setText("-")
            self.place_gadget_button.setChecked(False)
            self.place_gadget_button.setText("放置道具")
            self.place_ability_button.setChecked(False)
            self.place_ability_button.setText("放置技能")
            self.show_icon_box.setChecked(True)
            self.show_name_box.setChecked(False)
            self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
            self.operator_size_value_label.setText(f"{int(round(self._operator_scale * 100))}%")
            self.floor_value_label.setText(self._current_floor_key())
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
            gadget_key = target_definition.gadget_key if target_definition is not None else ""
            rotation = int(operator.rotation()) % 360 if operator is not None else (
                int(target_frame.rotation) % 360 if target_frame is not None else 0
            )
            floor_key = operator.floor_key if operator is not None else (
                target_frame.floor_key if target_frame is not None and target_frame.floor_key else self._current_floor_key()
            )
            show_icon = operator.show_icon if operator is not None else (
                target_frame.show_icon if target_frame is not None else True
            )
            show_name = operator.show_name if operator is not None else (
                target_frame.show_name if target_frame is not None else False
            )
            transition_mode = target_frame.transition_mode.value if target_frame is not None else OperatorTransitionMode.AUTO.value
            manual_interaction_ids = list(target_frame.manual_interaction_ids) if target_frame is not None else []
            if self._is_transition_mode_locked(target_operator_id):
                transition_mode = OperatorTransitionMode.AUTO.value
                manual_interaction_ids = []

            self.selection_label.setText(f"当前选中：{custom_name}")
            self.name_edit.setText(custom_name)
            self.side_combo.setCurrentIndex(0 if side == "attack" else 1)
            self._refresh_operator_combo(side, operator_key)
            self._refresh_gadget_combo(side, gadget_key)
            self.rotation_slider.setValue(rotation)
            self.rotation_value_label.setText(f"{rotation}°")
            gadget_asset = self._current_gadget_asset(operator_id)
            ability_entry = self._current_ability_entry(operator_id)
            gadget_count = self._current_gadget_used_count(operator_id)
            gadget_limit = gadget_asset.max_count if gadget_asset is not None else 0
            self.gadget_count_label.setText(
                f"已使用 {gadget_count} / {gadget_limit}" if gadget_asset is not None else "未选择"
            )
            self.place_gadget_button.setText("停止放置" if self._placing_gadget else "放置道具")
            self.place_gadget_button.setChecked(self._placing_gadget)
            self.ability_name_label.setText(
                (ability_entry.ability_name or ability_entry.key)
                if ability_entry is not None
                else "未配置"
            )
            ability_count = self._current_ability_used_count(operator_id)
            self.ability_count_label.setText(
                (
                    f"已使用 {ability_count} / {ability_entry.ability_max_count}"
                    if ability_entry is not None and ability_entry.ability_max_count > 0
                    else f"已使用 {ability_count} / 未配置"
                )
                if ability_entry is not None
                else "未配置"
            )
            self.place_ability_button.setText("停止放置" if self._placing_ability else "放置技能")
            self.place_ability_button.setChecked(self._placing_ability)
            self.show_icon_box.setChecked(show_icon)
            self.show_name_box.setChecked(show_name)
            self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
            self.operator_size_value_label.setText(f"{int(round(self._operator_scale * 100))}%")
            self.floor_value_label.setText(floor_key or self._current_floor_key())
            self._set_combo_value(self.transition_mode_combo, transition_mode)
            self._refresh_manual_interaction_controls(manual_interaction_ids)
            self._set_property_enabled(True)

        self._refresh_surface_property_panel(selected_surface)
        self._syncing_panel = False

        self._syncing_keyframe_panel = True
        self.keyframe_name_edit.setText(self._current_keyframe_name())
        self.keyframe_note_edit.setText(self._current_keyframe_note())
        self.keyframe_hint.setText(f"当前关键帧：{self._keyframe_label(self.current_keyframe_index)}")
        has_keyframe = 0 <= self.current_keyframe_index < len(self.keyframe_columns)
        self.keyframe_name_edit.setEnabled(has_keyframe)
        self.keyframe_note_edit.setEnabled(has_keyframe)
        self._syncing_keyframe_panel = False

    def _set_property_enabled(self, enabled: bool) -> None:
        self.name_edit.setEnabled(enabled)
        self.side_combo.setEnabled(enabled)
        self.operator_combo.setEnabled(enabled)
        self.gadget_combo.setEnabled(enabled)
        self.rotation_slider.setEnabled(enabled)
        self.show_icon_box.setEnabled(enabled)
        self.show_name_box.setEnabled(enabled)
        self.operator_size_slider.setEnabled(True)
        transition_editable = enabled and not self._is_transition_mode_locked(self._target_operator_id())
        self.transition_mode_combo.setEnabled(transition_editable)
        manual_enabled = (
            enabled
            and transition_editable
            and self.transition_mode_combo.currentData() == OperatorTransitionMode.MANUAL.value
        )
        self.manual_interaction_combo.setEnabled(manual_enabled)
        self.delete_operator_button.setEnabled(enabled)
        self.delete_operator_button.setVisible(enabled)
        self.gadget_label.setVisible(enabled)
        self.gadget_combo.setVisible(enabled)
        self.gadget_count_label.setVisible(enabled)
        self.place_gadget_button.setVisible(enabled)
        self.clear_gadget_button.setVisible(enabled)
        self.ability_label.setVisible(enabled)
        self.ability_name_label.setVisible(enabled)
        self.ability_count_label.setVisible(enabled)
        self.place_ability_button.setVisible(enabled)
        self.clear_ability_button.setVisible(enabled)
        gadget_asset = self._current_gadget_asset()
        can_place_gadget = enabled and gadget_asset is not None and 0 <= self.current_keyframe_index < len(self.keyframe_columns)
        self.place_gadget_button.setEnabled(can_place_gadget)
        self.clear_gadget_button.setEnabled(can_place_gadget and bool(self._current_gadget_positions()))
        ability_entry = self._current_ability_entry()
        can_place_ability = (
            enabled
            and ability_entry is not None
            and bool(ability_entry.ability_icon_path)
            and 0 <= self.current_keyframe_index < len(self.keyframe_columns)
        )
        self.place_ability_button.setEnabled(can_place_ability)
        self.clear_ability_button.setEnabled(can_place_ability and bool(self._current_ability_positions()))
        if not can_place_gadget and self._placing_gadget:
            self._placing_gadget = False
            self.place_gadget_button.setChecked(False)
            self.place_gadget_button.setText("放置道具")
        if not can_place_ability and self._placing_ability:
            self._placing_ability = False
            self.place_ability_button.setChecked(False)
            self.place_ability_button.setText("放置技能")

    def _refresh_manual_interaction_controls(self, selected_ids: list[str]) -> None:
        operator_id = self._target_operator_id()
        interactions = self._available_manual_interactions(operator_id, selected_ids)
        transition_locked = self._is_transition_mode_locked(operator_id)
        has_next_target = self._has_next_transition_target(operator_id)
        manual_mode_active = self.transition_mode_combo.currentData() == OperatorTransitionMode.MANUAL.value
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
        show_manual_controls = bool(operator_id) and not transition_locked and has_next_target and manual_mode_active
        self.manual_interaction_label.setVisible(show_manual_controls)
        self.manual_interaction_combo.setVisible(show_manual_controls)
        self.manual_interactions_hint.setVisible(show_manual_controls)
        if show_manual_controls:
            if not interactions:
                self.manual_interactions_hint.setText("当前步骤无可选互动点。")
                self.manual_interaction_combo.setEnabled(False)
            else:
                self.manual_interactions_hint.setText("选择当前步骤的互动点。")
        self._sync_scene_interaction_overlays(selected_ids)

    def _surface_state(self, surface_id: str) -> TacticalSurfaceState | None:
        return self.surface_states.get(surface_id)

    def _default_surface_state(self, surface_id: str) -> TacticalSurfaceState:
        return TacticalSurfaceState(surface_id=surface_id)

    def _surface_supports_openings(self, surface_id: str) -> bool:
        surface = next(
            (item for item in self._current_map_asset.surfaces if item.id == surface_id),
            None,
        ) if self._current_map_asset is not None else None
        return surface is not None and surface.kind == MapSurfaceType.SOFT_WALL

    def _normalized_surface_state(self, surface_id: str, state: TacticalSurfaceState) -> TacticalSurfaceState:
        normalized = deepcopy(state)
        if not self._surface_supports_openings(surface_id):
            normalized.opening_type = None
            normalized.foot_hole = False
            normalized.gun_hole = False
        if normalized.reinforced:
            normalized.opening_type = None
            normalized.foot_hole = False
            normalized.gun_hole = False
        elif normalized.opening_type is not None:
            normalized.foot_hole = False
            normalized.gun_hole = False
        return normalized

    def _set_surface_state(self, surface_id: str, state: TacticalSurfaceState | None) -> None:
        if state is None:
            self.surface_states.pop(surface_id, None)
        else:
            normalized = self._normalized_surface_state(surface_id, state)
            default_state = self._default_surface_state(surface_id)
            if normalized == default_state:
                self.surface_states.pop(surface_id, None)
            else:
                self.surface_states[surface_id] = normalized
        self._sync_scene_surface_overlays()
        self._refresh_property_panel()
        self._refresh_timeline()

    def _reinforced_surface_count(self) -> int:
        return sum(1 for state in self.surface_states.values() if state.reinforced)

    def _refresh_surface_property_panel(self, surface: MapSurface | None) -> None:
        state = self._surface_state(surface.id) if surface is not None else None
        self.surface_count_label.setText(f"加固数量：{self._reinforced_surface_count()} / 10")
        self.surface_opening_label.setVisible(True)
        self.opening_combo.setVisible(True)
        self.foot_hole_box.setVisible(True)
        self.gun_hole_box.setVisible(True)
        if surface is None:
            current_floor = self._current_floor_key()
            floor_surface_count = 0
            if self._current_map_asset is not None:
                floor_surface_count = sum(
                    1 for item in self._current_map_asset.surfaces if item.floor_key == current_floor
                )
            if floor_surface_count > 0:
                self.surface_selection_label.setText(f"当前装修：未选中（{floor_surface_count}）")
            else:
                self.surface_selection_label.setText("当前装修：无")
            self.reinforce_button.setText("加固")
            self.reinforce_button.setEnabled(False)
            self._set_combo_value(self.opening_combo, "")
            self.opening_combo.setEnabled(False)
            self.foot_hole_box.blockSignals(True)
            self.gun_hole_box.blockSignals(True)
            self.foot_hole_box.setChecked(False)
            self.gun_hole_box.setChecked(False)
            self.foot_hole_box.blockSignals(False)
            self.gun_hole_box.blockSignals(False)
            self.foot_hole_box.setEnabled(False)
            self.gun_hole_box.setEnabled(False)
            return

        self.surface_selection_label.setText(f"当前装修：{surface.id}")
        reinforced = bool(state and state.reinforced)
        supports_openings = self._surface_supports_openings(surface.id)
        self.reinforce_button.setText("取消加固" if reinforced else "加固")
        self.reinforce_button.setEnabled(True)
        opening_value = state.opening_type.value if state and state.opening_type is not None else ""
        self._set_combo_value(self.opening_combo, opening_value)
        self.surface_opening_label.setVisible(supports_openings)
        self.opening_combo.setVisible(supports_openings)
        self.foot_hole_box.setVisible(supports_openings)
        self.gun_hole_box.setVisible(supports_openings)
        self.opening_combo.setEnabled(supports_openings and not reinforced)
        self.foot_hole_box.blockSignals(True)
        self.gun_hole_box.blockSignals(True)
        self.foot_hole_box.setChecked(bool(state and state.foot_hole))
        self.gun_hole_box.setChecked(bool(state and state.gun_hole))
        self.foot_hole_box.blockSignals(False)
        self.gun_hole_box.blockSignals(False)
        holes_enabled = supports_openings and not reinforced and not opening_value
        self.foot_hole_box.setEnabled(holes_enabled)
        self.gun_hole_box.setEnabled(holes_enabled)

    def _toggle_selected_surface_reinforcement(self) -> None:
        if self._syncing_panel:
            return
        surface = self._selected_surface_asset()
        if surface is None:
            return
        before = self._capture_history_state()
        state = deepcopy(self._surface_state(surface.id) or self._default_surface_state(surface.id))
        if state.reinforced:
            state.reinforced = False
        else:
            if self._reinforced_surface_count() >= 10:
                MessageBox("加固数量已满", "当前战术最多允许 10 面加固墙体。", self).exec()
                return
            state.reinforced = True
        self._set_surface_state(surface.id, state)
        self._commit_history(before)

    def _update_selected_surface_opening(self, index: int) -> None:
        if self._syncing_panel:
            return
        surface = self._selected_surface_asset()
        if surface is None or not self._surface_supports_openings(surface.id):
            return
        before = self._capture_history_state()
        state = deepcopy(self._surface_state(surface.id) or self._default_surface_state(surface.id))
        opening_value = self.opening_combo.itemData(index) or ""
        state.opening_type = SurfaceOpeningType(opening_value) if opening_value else None
        self._set_surface_state(surface.id, state)
        self._commit_history(before)

    def _update_selected_surface_foot_hole(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        surface = self._selected_surface_asset()
        if surface is None or not self._surface_supports_openings(surface.id):
            return
        before = self._capture_history_state()
        state = deepcopy(self._surface_state(surface.id) or self._default_surface_state(surface.id))
        state.foot_hole = checked
        self._set_surface_state(surface.id, state)
        self._commit_history(before)

    def _update_selected_surface_gun_hole(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        surface = self._selected_surface_asset()
        if surface is None:
            return
        before = self._capture_history_state()
        state = deepcopy(self._surface_state(surface.id) or self._default_surface_state(surface.id))
        state.gun_hole = checked
        self._set_surface_state(surface.id, state)
        self._commit_history(before)

    def _build_project(self, project_path: str = "") -> TacticProject:
        scene = self._map_scene()
        return self.session_service.build_project(
            project_path=project_path or self.current_project_path,
            current_map_asset=self._current_map_asset,
            current_map_asset_path=self.current_map_asset_path,
            current_map_floor_key=self.current_map_floor_key,
            map_image_path=scene.current_map_path if scene is not None else "",
            operator_order=self.operator_order,
            operator_definitions=self.operator_definitions,
            keyframe_columns=self.keyframe_columns,
            keyframe_names=self.keyframe_names,
            keyframe_notes=self.keyframe_notes,
            surface_states=self.surface_states,
            current_keyframe_index=self.current_keyframe_index,
            transition_duration_ms=self._transition_duration_ms,
            operator_scale=self._operator_scale,
        )

    def _apply_project(self, project: TacticProject) -> None:
        self._pause_column_playback()
        scene = self._map_scene()
        if scene is None:
            return
        if project.map_info and project.map_info.metadata_path:
            if not self._load_map_asset(project.map_info.metadata_path, floor_key=project.map_info.current_floor_key):
                scene.clear_map()
                self.current_map_asset_path = ""
                self.current_map_floor_key = ""
                self._current_map_asset = None
                self._clear_overview_asset()
                self._rebuild_floor_panel()
        elif project.map_info and project.map_info.image_path:
            if scene.load_map_image(project.map_info.image_path):
                self.current_map_asset_path = ""
                self.current_map_floor_key = ""
                self._current_map_asset = None
                self._clear_overview_asset()
                self._rebuild_floor_panel()
        else:
            scene.clear_map()
            self.current_map_asset_path = ""
            self.current_map_floor_key = ""
            self._current_map_asset = None
            self._clear_overview_asset()
            self._rebuild_floor_panel()

        self.operator_order = list(project.operator_order)
        self.operator_definitions = {operator.id: deepcopy(operator) for operator in project.operators}
        self.keyframe_columns = [
            {state.id: deepcopy(state) for state in keyframe.operator_frames}
            for keyframe in project.timeline.keyframes
        ] or [{}]
        self.keyframe_names = [keyframe.name for keyframe in project.timeline.keyframes] or [""]
        self.keyframe_notes = [keyframe.note for keyframe in project.timeline.keyframes] or [""]
        self.surface_states = {
            state.surface_id: self._normalized_surface_state(state.surface_id, deepcopy(state))
            for state in project.surface_states
            if self._normalized_surface_state(state.surface_id, deepcopy(state)) != self._default_surface_state(state.surface_id)
        }
        self.current_keyframe_index = min(project.current_keyframe_index, len(self.keyframe_columns) - 1)
        self.current_timeline_row = -1
        self.current_surface_id = ""
        self._transition_duration_ms = project.transition_duration_ms
        self._operator_scale = project.operator_scale
        self.playback_duration_slider.setValue(self._transition_duration_ms)
        self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
        self._apply_operator_scale_to_views()
        self._update_view_mode_availability()

        for operator_id in self.operator_definitions:
            if operator_id not in self.operator_order:
                self.operator_order.append(operator_id)
        for frame in self.keyframe_columns:
            for state in frame.values():
                if state.id not in self.operator_order:
                    self.operator_order.append(state.id)

        self._apply_timeline_column(self.current_keyframe_index)
        self._refresh_timeline()

    def _capture_project_state(self) -> EditorProjectState:
        scene = self._map_scene()
        map_reference_path = self.current_map_asset_path
        if not map_reference_path and scene is not None:
            map_reference_path = scene.current_map_path
        return EditorProjectState(
            map_reference_path=map_reference_path,
            operator_order=list(self.operator_order),
            operator_definitions=deepcopy(self.operator_definitions),
            keyframe_columns=deepcopy(self.keyframe_columns),
            keyframe_names=list(self.keyframe_names),
            keyframe_notes=list(self.keyframe_notes),
            surface_states=deepcopy(self.surface_states),
            transition_duration_ms=self._transition_duration_ms,
            operator_scale=self._operator_scale,
        )

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
            selected_surface_id=self.current_surface_id,
            surface_states=deepcopy(self.surface_states),
            transition_duration_ms=self._transition_duration_ms,
            operator_scale=self._operator_scale,
        )

    def _restore_history_state(self, snapshot: EditorHistoryState) -> None:
        scene = self._map_scene()
        if scene is None:
            return
        self._history_lock = True
        self._pause_column_playback()
        if snapshot.map_asset_path:
            if not self._load_map_asset(snapshot.map_asset_path, floor_key=snapshot.map_floor_key, fit_view=False):
                scene.clear_map()
                self.current_map_asset_path = ""
                self.current_map_floor_key = ""
                self._current_map_asset = None
                self._clear_overview_asset()
                self._rebuild_floor_panel()
        else:
            if snapshot.map_image_path:
                scene.load_map_image(snapshot.map_image_path)
            else:
                scene.clear_map()
            self.current_map_asset_path = ""
            self.current_map_floor_key = ""
            self._current_map_asset = None
            self._clear_overview_asset()
            self._rebuild_floor_panel()

        self.operator_order = list(snapshot.operator_order)
        self.operator_definitions = deepcopy(snapshot.operator_definitions)
        self.keyframe_columns = deepcopy(snapshot.keyframe_columns)
        self.keyframe_names = list(snapshot.keyframe_names)
        self.keyframe_notes = list(snapshot.keyframe_notes)
        self.current_keyframe_index = snapshot.current_keyframe_index
        self.current_timeline_row = snapshot.current_timeline_row
        self.current_surface_id = snapshot.selected_surface_id
        self.surface_states = deepcopy(snapshot.surface_states)
        self._transition_duration_ms = snapshot.transition_duration_ms
        self._operator_scale = snapshot.operator_scale
        self.playback_duration_slider.setValue(self._transition_duration_ms)
        self.operator_size_slider.setValue(int(round(self._operator_scale * 100)))
        self._apply_operator_scale_to_views()

        scene.sync_operator_states(deepcopy(snapshot.scene_states), snapshot.selected_operator_id or None)
        self._sync_scene_surface_overlays()
        for operator in scene.operator_items():
            self._update_operator_icon(operator)
        self._sync_overview_scene_states(self._resolved_states(self.current_keyframe_index, include_all_floors=True))
        self._refresh_property_panel()
        self._history_lock = False
        self._refresh_timeline()

    def refresh_theme(self) -> None:
        self.setStyleSheet(page_stylesheet(self.objectName()))
        self.property_panel.refresh_theme()
        self.floor_panel.refresh_theme()
        self.playback_panel.refresh_theme()
        self.timeline.refresh_theme()
        self.map_view.refresh_theme()
        self.overview_view.refresh_theme()
        self.canvas_stack.update()

    @staticmethod
    def _sort_operator_id(operator_id: str) -> int:
        try:
            return int(operator_id)
        except ValueError:
            return 0
