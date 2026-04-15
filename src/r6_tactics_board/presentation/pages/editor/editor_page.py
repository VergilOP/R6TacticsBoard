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
from r6_tactics_board.presentation.pages.editor.editor_playback import EditorPlaybackMixin
from r6_tactics_board.presentation.pages.editor.editor_properties import EditorPropertyPanelMixin
from r6_tactics_board.presentation.pages.editor.editor_project_state import EditorProjectStateMixin
from r6_tactics_board.presentation.pages.editor.editor_scene_sync import EditorSceneSyncMixin
from r6_tactics_board.presentation.pages.editor.editor_views import EditorViewSyncMixin
from r6_tactics_board.presentation.pages.editor.editor_timeline import EditorTimelineContextMixin
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


class EditorPage(
    EditorViewSyncMixin,
    EditorPlaybackMixin,
    EditorProjectStateMixin,
    EditorSceneSyncMixin,
    EditorPropertyPanelMixin,
    EditorTimelineContextMixin,
    EditorTokenWorkflowMixin,
    QWidget,
):
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

    def _manual_interaction_prefix(
        self,
        start_floor: str,
        manual_interaction_ids: list[str],
    ) -> tuple[list[tuple[MapInteractionPoint, str]], str] | None:
        return self._route_planner().manual_interaction_prefix(start_floor, manual_interaction_ids)

    def _can_reach_floor(self, start_floor: str | None, end_floor: str) -> bool:
        return self._route_planner().can_reach_floor(start_floor, end_floor)
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

    def _operator_row(self, operator_id: str) -> int:
        try:
            return self.operator_order.index(operator_id)
        except ValueError:
            return -1

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
