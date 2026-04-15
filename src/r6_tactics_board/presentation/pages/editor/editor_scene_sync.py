from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import QPointF
from qfluentwidgets import MessageBox

from r6_tactics_board.domain.models import (
    MapSurface,
    OperatorDefinition,
    OperatorDisplayMode,
    OperatorFrameState,
    OperatorTransitionMode,
    Point2D,
    TeamSide,
    resolve_operator_state,
)


class EditorSceneSyncMixin:
    """Canvas refresh and selection-sync workflow helper."""

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

    def _current_preview_routes(self) -> dict[str, list]:
        routes: dict[str, list] = {}
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

    def _current_preview_segments(self) -> dict[str, tuple]:
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
    ) -> dict[str, tuple]:
        segments: dict[str, tuple] = {}
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
        start_state,
        end_state,
        route: list,
        progress: float,
    ):
        return self._route_planner().preview_segment_on_route(
            start_state,
            end_state,
            route,
            progress,
            current_floor_key=self._current_floor_key(),
        )

    def _current_placement_state(self):
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
    def _same_position(first, second) -> bool:
        return (
            abs(first.position.x - second.position.x) < 0.1
            and abs(first.position.y - second.position.y) < 0.1
        )

    def _selected_surface_asset(self) -> MapSurface | None:
        if self._current_map_asset is None or not self.current_surface_id:
            return None
        for surface in self._current_map_asset.surfaces:
            if surface.id == self.current_surface_id:
                return surface
        return None

    def _update_operator_icon(self, operator) -> None:
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

    def _frame_state_from_operator(self, operator) -> OperatorFrameState | None:
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
        self.keyframe_columns = self._timeline_controller().set_cell(
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
                self.keyframe_columns = self._timeline_controller().set_cell(
                    self.keyframe_columns,
                    self.current_keyframe_index,
                    operator.operator_id,
                    state,
                )
        self._refresh_timeline()
        self._commit_history(before)

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

    def _current_operator(self):
        scene = self._map_scene()
        if scene is None:
            return None
        return scene.selected_operator()

    def _current_surface(self):
        scene = self._map_scene()
        if scene is None:
            return None
        return scene.selected_surface()

    def _timeline_controller(self):
        from r6_tactics_board.application.timeline.timeline_editor import TimelineEditorController

        return TimelineEditorController
