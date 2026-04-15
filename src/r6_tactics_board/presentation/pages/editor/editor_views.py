from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import QPoint, QPointF, QRect, QTimer

from r6_tactics_board.domain.models import MapInteractionPoint, MapInteractionType, MapSurfaceType, OperatorState, Point2D


class EditorViewSyncMixin:
    """Map / overview view synchronization helper."""

    def _map_scene(self):
        from r6_tactics_board.presentation.widgets.canvas.map_scene import MapScene

        scene = self.map_view.scene()
        if isinstance(scene, MapScene):
            return scene
        return None

    def _overview_scene(self):
        return self.overview_view.overview_scene()

    def _sync_overview_asset(self, asset, *, reset_camera: bool) -> bool:
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
        scene,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list,
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

    def _active_canvas_widget(self):
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

    def _route_planner(self):
        return self._route_planner_factory(self._transition_interactions())

    def _route_planner_factory(self, interactions: list[MapInteractionPoint]):
        from r6_tactics_board.application.routing.interaction_routing import InteractionRoutePlanner

        return InteractionRoutePlanner(interactions)

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
