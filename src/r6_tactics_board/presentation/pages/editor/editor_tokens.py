from __future__ import annotations

from copy import deepcopy

from r6_tactics_board.domain.models import OperatorFrameState, Point2D


class EditorTokenWorkflowMixin:
    """Token workflow helper for gadget and ability placement.

    This mixin keeps one-time vs persistent token semantics out of the main
    page body so the editor page can focus on page-level orchestration.
    """

    def _toggle_gadget_placement_mode(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        gadget_asset = self._current_gadget_asset()
        if checked and gadget_asset is None:
            self._placing_gadget = False
            self.place_gadget_button.blockSignals(True)
            self.place_gadget_button.setChecked(False)
            self.place_gadget_button.blockSignals(False)
            self.place_gadget_button.setText("放置道具")
            self._sync_scene_placement_target()
            return
        if checked and self._placing_ability:
            self._placing_ability = False
            self.place_ability_button.blockSignals(True)
            self.place_ability_button.setChecked(False)
            self.place_ability_button.blockSignals(False)
            self.place_ability_button.setText("放置技能")
        self._placing_gadget = checked
        if checked:
            self.current_surface_id = ""
            scene = self._map_scene()
            if scene is not None and scene.selected_surface() is not None:
                scene.clearSelection()
            operator_id = self._target_operator_id()
            if operator_id is not None:
                self._activate_property_section("operator", context=("operator", operator_id), force=True)
        self.place_gadget_button.setText("停止放置" if checked else "放置道具")
        self._sync_scene_placement_target()
        self._refresh_property_panel()
        self._refresh_timeline()

    def _toggle_ability_placement_mode(self, checked: bool) -> None:
        if self._syncing_panel:
            return
        ability_entry = self._current_ability_entry()
        if checked and (ability_entry is None or not ability_entry.ability_icon_path):
            self._placing_ability = False
            self.place_ability_button.blockSignals(True)
            self.place_ability_button.setChecked(False)
            self.place_ability_button.blockSignals(False)
            self.place_ability_button.setText("放置技能")
            self._sync_scene_placement_target()
            return
        if checked and self._placing_gadget:
            self._placing_gadget = False
            self.place_gadget_button.blockSignals(True)
            self.place_gadget_button.setChecked(False)
            self.place_gadget_button.blockSignals(False)
            self.place_gadget_button.setText("放置道具")
        self._placing_ability = checked
        if checked:
            self.current_surface_id = ""
            scene = self._map_scene()
            if scene is not None and scene.selected_surface() is not None:
                scene.clearSelection()
            operator_id = self._target_operator_id()
            if operator_id is not None:
                self._activate_property_section("operator", context=("operator", operator_id), force=True)
        self.place_ability_button.setText("停止放置" if checked else "放置技能")
        self._sync_scene_placement_target()
        self._refresh_property_panel()
        self._refresh_timeline()

    def _on_gadget_placed(self, operator_id: str, x: float, y: float) -> None:
        if not self._placing_gadget or operator_id != (self._target_operator_id() or ""):
            return
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        gadget_asset = self._current_gadget_asset(operator_id)
        if gadget_asset is None:
            return

        before = self._capture_history_state()
        frame = self._current_transition_frame(operator_id)
        if frame is None:
            frame = OperatorFrameState(
                id=operator_id,
                position=Point2D(x=0, y=0),
                floor_key=self._current_floor_key(),
            )
        frame = deepcopy(frame)
        frame.floor_key = self._current_floor_key()
        used_count = (
            int(frame.gadget_used_count)
            if frame.gadget_used_count is not None
            else len(frame.gadget_positions or [])
        )
        if used_count >= gadget_asset.max_count:
            return
        positions = [
            Point2D(x=item.x, y=item.y)
            for item in (frame.gadget_positions or [])
            if abs(item.x - x) >= 0.1 or abs(item.y - y) >= 0.1
        ]
        used_count += 1
        frame.gadget_used_count = used_count
        if gadget_asset.persists_on_map:
            positions.append(Point2D(x=x, y=y))
            frame.gadget_positions = positions
        else:
            frame.gadget_positions = positions + [Point2D(x=x, y=y)]
        self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
        self._apply_timeline_column(self.current_keyframe_index)
        self._commit_history(before)

    def _on_ability_placed(self, operator_id: str, x: float, y: float) -> None:
        if not self._placing_ability or operator_id != (self._target_operator_id() or ""):
            return
        if not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        ability_entry = self._current_ability_entry(operator_id)
        if ability_entry is None or not ability_entry.ability_icon_path:
            return

        before = self._capture_history_state()
        frame = self._current_transition_frame(operator_id)
        if frame is None:
            frame = OperatorFrameState(
                id=operator_id,
                position=Point2D(x=0, y=0),
                floor_key=self._current_floor_key(),
            )
        frame = deepcopy(frame)
        frame.floor_key = self._current_floor_key()
        used_count = (
            int(frame.ability_used_count)
            if frame.ability_used_count is not None
            else len(frame.ability_positions or [])
        )
        if ability_entry.ability_max_count > 0 and used_count >= ability_entry.ability_max_count:
            return
        positions = [
            Point2D(x=item.x, y=item.y)
            for item in (frame.ability_positions or [])
            if abs(item.x - x) >= 0.1 or abs(item.y - y) >= 0.1
        ]
        used_count += 1
        frame.ability_used_count = used_count
        if ability_entry.ability_persists_on_map:
            positions.append(Point2D(x=x, y=y))
            frame.ability_positions = positions
        else:
            frame.ability_positions = positions + [Point2D(x=x, y=y)]
        self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
        self._apply_timeline_column(self.current_keyframe_index)
        self._commit_history(before)

    def _current_ability_entry(self, operator_id: str | None = None):
        if operator_id is None:
            operator_id = self._target_operator_id()
        if operator_id is None:
            return None
        definition = self.operator_definitions.get(operator_id)
        if definition is None or not definition.operator_key:
            return None
        return self.session_service.find_operator_catalog_entry(definition.operator_key, definition.side.value)

    def _current_gadget_asset(self, operator_id: str | None = None):
        if operator_id is None:
            operator_id = self._target_operator_id()
        if operator_id is None:
            return None
        definition = self.operator_definitions.get(operator_id)
        if definition is None or not definition.gadget_key:
            return None
        return self.session_service.find_operator_gadget_asset(
            definition.side.value,
            definition.operator_key,
            definition.gadget_key,
        )

    def _current_gadget_positions(self, operator_id: str | None = None) -> list[Point2D]:
        if operator_id is None:
            operator_id = self._target_operator_id()
        if operator_id is None:
            return []
        state = self._resolved_state(operator_id, self.current_keyframe_index)
        if state is None:
            return []
        return [Point2D(x=item.x, y=item.y) for item in state.gadget_positions]

    def _current_gadget_used_count(self, operator_id: str | None = None) -> int:
        if operator_id is None:
            operator_id = self._target_operator_id()
        if operator_id is None:
            return 0
        state = self._resolved_state(operator_id, self.current_keyframe_index)
        if state is None:
            return 0
        return max(0, int(state.gadget_used_count))

    def _current_ability_positions(self, operator_id: str | None = None) -> list[Point2D]:
        if operator_id is None:
            operator_id = self._target_operator_id()
        if operator_id is None:
            return []
        state = self._resolved_state(operator_id, self.current_keyframe_index)
        if state is None:
            return []
        return [Point2D(x=item.x, y=item.y) for item in state.ability_positions]

    def _current_ability_used_count(self, operator_id: str | None = None) -> int:
        if operator_id is None:
            operator_id = self._target_operator_id()
        if operator_id is None:
            return 0
        state = self._resolved_state(operator_id, self.current_keyframe_index)
        if state is None:
            return 0
        return max(0, int(state.ability_used_count))

    def _clear_current_frame_gadget_placements(self) -> None:
        operator_id = self._target_operator_id()
        if operator_id is None or not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        before = self._capture_history_state()
        frame = self._current_transition_frame(operator_id)
        if frame is None:
            return
        explicit_frame = self._explicit_current_frame(operator_id)
        removed_count = len(explicit_frame.gadget_positions or []) if explicit_frame is not None else 0
        if removed_count == 0 and not frame.gadget_positions:
            return
        frame.gadget_positions = []
        previous_frame = self._resolved_frame_state(operator_id, self.current_keyframe_index - 1) if self.current_keyframe_index > 0 else None
        inherited_count = previous_frame.gadget_used_count if previous_frame is not None else 0
        current_count = int(frame.gadget_used_count or 0)
        if removed_count > 0:
            frame.gadget_used_count = max(inherited_count, current_count - removed_count)
        self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
        self._apply_timeline_column(self.current_keyframe_index)
        self._commit_history(before)

    def _clear_current_frame_ability_placements(self) -> None:
        operator_id = self._target_operator_id()
        if operator_id is None or not (0 <= self.current_keyframe_index < len(self.keyframe_columns)):
            return
        before = self._capture_history_state()
        frame = self._current_transition_frame(operator_id)
        if frame is None:
            return
        explicit_frame = self._explicit_current_frame(operator_id)
        removed_count = len(explicit_frame.ability_positions or []) if explicit_frame is not None else 0
        if removed_count == 0 and not frame.ability_positions:
            return
        frame.ability_positions = []
        previous_frame = self._resolved_frame_state(operator_id, self.current_keyframe_index - 1) if self.current_keyframe_index > 0 else None
        inherited_count = previous_frame.ability_used_count if previous_frame is not None else 0
        current_count = int(frame.ability_used_count or 0)
        if removed_count > 0:
            frame.ability_used_count = max(inherited_count, current_count - removed_count)
        self.keyframe_columns[self.current_keyframe_index][operator_id] = frame
        self._apply_timeline_column(self.current_keyframe_index)
        self._commit_history(before)

    def _clear_operator_gadget_deployments(self, operator_id: str) -> None:
        for column in self.keyframe_columns:
            frame = column.get(operator_id)
            if frame is None:
                continue
            if frame.gadget_positions or frame.gadget_used_count is not None:
                frame = deepcopy(frame)
                frame.gadget_positions = []
                frame.gadget_used_count = 0
                column[operator_id] = frame

    def _clear_operator_ability_deployments(self, operator_id: str) -> None:
        for column in self.keyframe_columns:
            frame = column.get(operator_id)
            if frame is None:
                continue
            if frame.ability_positions or frame.ability_used_count is not None:
                frame = deepcopy(frame)
                frame.ability_positions = []
                frame.ability_used_count = 0
                column[operator_id] = frame
