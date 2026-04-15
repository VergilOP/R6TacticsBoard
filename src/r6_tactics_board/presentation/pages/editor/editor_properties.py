from __future__ import annotations

from PyQt6.QtCore import QTimer

from r6_tactics_board.domain.models import MapInteractionPoint, MapInteractionType, OperatorTransitionMode
from r6_tactics_board.infrastructure.diagnostics.debug_logging import debug_log


class EditorPropertyPanelMixin:
    """Property-panel workflow helper.

    Keeps right-side panel refresh and context-sensitive visibility logic out
    of the main editor page so the page body can focus on orchestration.
    """

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
            self.floor_value_label.setText(f"{floor_key or self._current_floor_key()}")
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

    def _current_transition_states(
        self,
        operator_id: str | None,
    ):
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
        self._queue_property_panel_refresh(self._clear_manual_interaction_hover)

    def _schedule_property_panel_refresh(self) -> None:
        self._queue_property_panel_refresh(self._refresh_property_panel)

    def _queue_property_panel_refresh(self, callback) -> None:
        if self._property_panel_refresh_pending:
            return
        self._property_panel_refresh_pending = True

        def run() -> None:
            self._property_panel_refresh_pending = False
            debug_log("editor: deferred property panel refresh")
            callback()

        QTimer.singleShot(0, run)
