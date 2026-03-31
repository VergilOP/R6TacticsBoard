from copy import deepcopy
from dataclasses import dataclass
from math import cos, radians, sin

import numpy as np
from PyQt6.QtGui import QColor, QFont, QImage, QPixmap, QVector3D
from pyqtgraph.opengl import GLImageItem, GLLinePlotItem, GLTextItem

from r6_tactics_board.application.routing.interaction_routing import PlaybackRouteSegment
from r6_tactics_board.domain.models import OperatorDisplayMode, OperatorState, Point2D
from r6_tactics_board.infrastructure.assets.asset_registry import AssetRegistry, MapAsset, MapFloorAsset
from r6_tactics_board.presentation.styles.theme import overview_label_color, overview_route_rgba
from r6_tactics_board.presentation.widgets.canvas.overview_projection import (
    FloorOverviewLayout,
    OverviewProjection,
)


@dataclass(slots=True)
class OverviewOperatorOverlay:
    operator_id: str
    world_position: tuple[float, float, float]
    world_forward: tuple[float, float, float]
    operator_key: str
    custom_name: str
    display_mode: str
    icon_pixmap: QPixmap
    selected: bool


class OverviewScene:
    def __init__(self, view) -> None:
        self._view = view
        self._projection = OverviewProjection()
        self._asset_registry = AssetRegistry()
        self._asset: MapAsset | None = None
        self._floor_items: dict[str, GLImageItem] = {}
        self._floor_labels: dict[str, GLTextItem] = {}
        self._floor_layouts: dict[str, FloorOverviewLayout] = {}
        self._states: dict[str, OperatorState] = {}
        self._selected_operator_id = ""
        self._visible_floor_keys: set[str] = set()
        self._render_position_overrides: dict[str, tuple[float, float, float]] = {}
        self._route_items: dict[str, GLLinePlotItem] = {}
        self._routes: dict[str, list[PlaybackRouteSegment]] = {}
        self._icon_cache: dict[tuple[str, str], QPixmap] = {}

    @property
    def asset(self) -> MapAsset | None:
        return self._asset

    def clear_map(self) -> None:
        for item in self._floor_items.values():
            self._view.removeItem(item)
        for item in self._floor_labels.values():
            self._view.removeItem(item)
        for item in self._route_items.values():
            self._view.removeItem(item)
        self._floor_items = {}
        self._floor_labels = {}
        self._floor_layouts = {}
        self._route_items = {}
        self._routes = {}
        self._states = {}
        self._selected_operator_id = ""
        self._visible_floor_keys = set()
        self._render_position_overrides = {}
        self._asset = None

    def set_map_asset(self, asset: MapAsset | None) -> bool:
        self.clear_map()
        if asset is None:
            return True

        textures: dict[str, tuple[np.ndarray, int, int]] = {}
        ordered_floors = self._projection.ordered_floors(asset)
        for floor in ordered_floors:
            image = QImage(floor.image_path)
            if image.isNull():
                continue
            rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
            width = rgba.width()
            height = rgba.height()
            buffer = rgba.bits().asstring(rgba.sizeInBytes())
            data = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
            texture = np.ascontiguousarray(np.transpose(np.flipud(data), (1, 0, 2)))
            textures[floor.key] = (texture, width, height)

        if not textures:
            return False

        dimensions = {
            floor_key: (width, height)
            for floor_key, (_, width, height) in textures.items()
        }
        self._asset = asset
        self._floor_layouts = self._projection.floor_layouts(asset, dimensions)
        self._visible_floor_keys = {floor.key for floor in ordered_floors}

        for floor in ordered_floors:
            if floor.key not in textures or floor.key not in self._floor_layouts:
                continue
            data, width, height = textures[floor.key]
            layout = self._floor_layouts[floor.key]

            floor_item = GLImageItem(data, smooth=True, glOptions="translucent")
            floor_item.translate(-width / 2.0, -height / 2.0, layout.z)
            self._view.addItem(floor_item)
            self._floor_items[floor.key] = floor_item

            label = GLTextItem(
                pos=(-(width / 2.0) + 24.0, (height / 2.0) - 24.0, layout.z + 4.0),
                color=overview_label_color(),
                text=floor.name,
                font=QFont("Microsoft YaHei UI", 11),
            )
            self._view.addItem(label)
            self._floor_labels[floor.key] = label

        self._update_camera_defaults()
        self._apply_floor_visibility()
        self._view.update()
        return True

    def reset_camera(self) -> None:
        self._update_camera_defaults()

    def sync_operator_states(
        self,
        states: list[OperatorState],
        *,
        selected_operator_id: str = "",
    ) -> None:
        self._selected_operator_id = selected_operator_id
        self._states = {
            state.id: deepcopy(state)
            for state in states
        }
        self._view.update()

    def set_render_position_overrides(
        self,
        overrides: dict[str, tuple[float, float, float]],
    ) -> None:
        self._render_position_overrides = dict(overrides)
        self._view.update()

    def set_visible_floors(self, floor_keys: set[str]) -> None:
        self._visible_floor_keys = set(floor_keys)
        self._apply_floor_visibility()
        self._view.update()
        if self._route_items:
            for operator_id, item in list(self._route_items.items()):
                if item is not None:
                    item.hide()

    def set_preview_routes(self, routes: dict[str, list[PlaybackRouteSegment]]) -> None:
        self._routes = {
            operator_id: list(segments)
            for operator_id, segments in routes.items()
        }
        existing_ids = set(self._route_items)
        incoming_ids = {
            operator_id
            for operator_id, segments in routes.items()
            if segments
        }

        for operator_id in existing_ids - incoming_ids:
            item = self._route_items.pop(operator_id)
            self._view.removeItem(item)

        for operator_id in incoming_ids:
            points = self._route_points(routes[operator_id])
            if points.shape[0] < 2:
                continue
            item = self._route_items.get(operator_id)
            if item is None:
                item = GLLinePlotItem(mode="line_strip", antialias=True)
                self._route_items[operator_id] = item
                self._view.addItem(item)
            selected = operator_id == self._selected_operator_id
            item.setData(
                pos=points,
                color=overview_route_rgba(selected),
                width=3.0 if selected else 1.5,
            )
            item.setVisible(points.shape[0] >= 2)

    def overlay_operators(self) -> list[OverviewOperatorOverlay]:
        overlays: list[OverviewOperatorOverlay] = []
        for operator_id, state in sorted(
            self._states.items(),
            key=lambda item: int(item[0]) if item[0].isdigit() else 0,
        ):
            layout = self._floor_layouts.get(state.floor_key)
            if layout is None:
                continue
            if self._visible_floor_keys and state.floor_key not in self._visible_floor_keys:
                continue
            x, y, z = self._render_position_overrides.get(
                operator_id,
                self._projection.point_to_world(layout, state.position),
            )
            rad = radians(state.rotation)
            forward = (
                x + sin(rad) * 36.0,
                y + cos(rad) * 36.0,
                z + 8.0,
            )
            overlays.append(
                OverviewOperatorOverlay(
                    operator_id=operator_id,
                    world_position=(x, y, z + 8.0),
                    world_forward=forward,
                    operator_key=state.operator_key,
                    custom_name=state.custom_name,
                    display_mode=state.display_mode.value,
                    icon_pixmap=self._operator_icon(state.side.value, state.operator_key),
                    selected=operator_id == self._selected_operator_id,
                )
            )
        return overlays

    def _route_points(self, segments: list[PlaybackRouteSegment]) -> np.ndarray:
        points: list[list[float]] = []
        for segment in segments:
            if self._visible_floor_keys and segment.floor_key not in self._visible_floor_keys:
                continue
            start_layout = self._floor_layouts.get(segment.floor_key)
            end_layout = self._floor_layouts.get(segment.result_floor_key or segment.floor_key)
            if start_layout is None or end_layout is None:
                continue

            start = self._projection.point_to_world(start_layout, segment.start)
            end_same_floor = self._projection.point_to_world(start_layout, segment.end)
            points.append([start[0], start[1], start[2] + 6.0])
            points.append([end_same_floor[0], end_same_floor[1], end_same_floor[2] + 6.0])
            if (
                segment.result_floor_key
                and segment.result_floor_key != segment.floor_key
                and (
                    not self._visible_floor_keys
                    or segment.result_floor_key in self._visible_floor_keys
                )
            ):
                end_next_floor = self._projection.point_to_world(end_layout, segment.end)
                points.append([end_next_floor[0], end_next_floor[1], end_next_floor[2] + 6.0])

        if not points:
            return np.empty((0, 3), dtype=np.float32)
        return np.asarray(points, dtype=np.float32)

    def _update_camera_defaults(self) -> None:
        distance = self._projection.default_distance(self._floor_layouts)
        center_x, center_y, center_z = self._projection.default_center(self._floor_layouts)
        overview = self._asset.overview_2p5d if self._asset is not None else None
        azimuth = overview.default_yaw if overview is not None else 215.0

        self._view.opts["center"] = QVector3D(center_x, center_y, center_z)
        self._view.opts["distance"] = distance
        self._view.opts["elevation"] = 28.0
        self._view.opts["azimuth"] = azimuth
        self._view.opts["fov"] = 55.0
        self._view.update()

    def _apply_floor_visibility(self) -> None:
        for floor_key, item in self._floor_items.items():
            visible = not self._visible_floor_keys or floor_key in self._visible_floor_keys
            item.setVisible(visible)
        for floor_key, label in self._floor_labels.items():
            visible = not self._visible_floor_keys or floor_key in self._visible_floor_keys
            label.setVisible(visible)

    def _operator_icon(self, side: str, operator_key: str) -> QPixmap:
        cache_key = (side, operator_key)
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        asset = self._asset_registry.find_operator_asset(side, operator_key)
        pixmap = QPixmap(asset.path) if asset is not None else QPixmap()
        self._icon_cache[cache_key] = pixmap
        return pixmap

    def world_point(
        self,
        floor_key: str,
        x: float,
        y: float,
        *,
        z_offset: float = 0.0,
    ) -> tuple[float, float, float] | None:
        layout = self._floor_layouts.get(floor_key)
        if layout is None:
            return None
        wx, wy, wz = self._projection.point_to_world(layout, Point2D(x=x, y=y))
        return (wx, wy, wz + z_offset)

    def refresh_theme(self) -> None:
        if self._asset is None:
            return

        asset = self._asset
        states = list(self._states.values())
        selected_operator_id = self._selected_operator_id
        visible_floor_keys = set(self._visible_floor_keys)
        render_position_overrides = dict(self._render_position_overrides)
        routes = {
            operator_id: list(segments)
            for operator_id, segments in self._routes.items()
        }

        self.set_map_asset(asset)
        self.sync_operator_states(states, selected_operator_id=selected_operator_id)
        self.set_visible_floors(visible_floor_keys)
        self.set_render_position_overrides(render_position_overrides)
        self.set_preview_routes(routes)
