from __future__ import annotations


class EditorTimelineContextMixin:
    """Timeline and current-context workflow helper.

    Keeps column switching, context sync, and timeline refresh behavior
    separate from the page construction code.
    """

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
