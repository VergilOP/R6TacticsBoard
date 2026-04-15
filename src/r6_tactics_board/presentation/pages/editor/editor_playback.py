from __future__ import annotations

from copy import deepcopy

from r6_tactics_board.domain.models import MapInteractionType, OperatorState, OperatorTransitionMode, Point2D


class EditorPlaybackMixin:
    """Playback and cross-floor route workflow helper."""

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
    ) -> dict[str, list]:
        routes: dict[str, list] = {}
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
    ) -> list:
        mode, manual_ids = self._transition_settings_for_operator(operator_id, from_column)
        return self._build_transition_route(start_state, end_state, mode, manual_ids)

    def _build_transition_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        transition_mode: OperatorTransitionMode = OperatorTransitionMode.AUTO,
        manual_interaction_ids: list[str] | None = None,
    ) -> list:
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
        route: list,
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
        routes: dict[str, list],
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
    def _route_floor_change_count(route: list) -> int:
        return sum(
            1
            for segment in route
            if segment.result_floor_key and segment.result_floor_key != segment.floor_key
        )

    def _route_total_duration_ms(self, route: list) -> float:
        return float(self._transition_duration_ms) + sum(
            self._transition_duration_for_segment(route, segment)
            for segment in route
            if segment.result_floor_key and segment.result_floor_key != segment.floor_key
        )

    def _transition_duration_for_segment(
        self,
        route: list,
        segment,
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

    def _transition_segment_weight(self, segment) -> float:
        planner = self._route_planner()
        length = planner.transition_path_length(segment)
        if length > 0.001:
            return length
        return 1.0

    def _route_phase_at_elapsed(
        self,
        route: list,
        elapsed_ms: float,
    ) -> tuple[str, object | None, float]:
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
        route: list,
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
