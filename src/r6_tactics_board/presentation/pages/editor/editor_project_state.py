from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox, QWidget

from r6_tactics_board.presentation.pages.editor.editor_models import (
    EditorHistoryState,
    EditorProjectState,
)


class EditorProjectStateMixin:
    """Project build/apply/history workflow helper."""

    def _build_project(self, project_path: str = ""):
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

    def _apply_project(self, project) -> None:
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

    def _capture_project_state(self):
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

    def _capture_history_state(self):
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

    def _commit_history(self, before) -> None:
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

    def _restore_history_state(self, snapshot) -> None:
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
