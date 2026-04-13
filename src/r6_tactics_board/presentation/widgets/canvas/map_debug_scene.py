from copy import deepcopy
from math import atan2, cos, degrees, hypot, radians, sin

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
)

from r6_tactics_board.domain.models import MapInteractionPoint, MapSurface, MapSurfaceType
from r6_tactics_board.infrastructure.diagnostics.debug_logging import debug_log
from r6_tactics_board.presentation.styles.theme import canvas_background_color, canvas_grid_color
from r6_tactics_board.presentation.widgets.canvas.map_interaction_item import MapInteractionItem
from r6_tactics_board.presentation.widgets.canvas.map_surface_item import MapSurfaceItem


class MapDebugScene(QGraphicsScene):
    DEFAULT_SURFACE_ENDPOINT_SNAP_DISTANCE = 10.0

    interaction_selected = pyqtSignal(str)
    interaction_moved = pyqtSignal(str, float, float)
    interaction_place_requested = pyqtSignal(object)
    surface_selected = pyqtSignal(str)
    surface_moved = pyqtSignal(str, float, float, float, float)
    surface_place_requested = pyqtSignal(str, float, float, float, float)

    def __init__(self) -> None:
        super().__init__()
        self._map_item: QGraphicsPixmapItem | None = None
        self._items_by_id: dict[str, MapInteractionItem] = {}
        self._surface_items: dict[str, MapSurfaceItem] = {}
        self._interactions: list[MapInteractionPoint] = []
        self._surfaces: list[MapSurface] = []
        self._grid_items = []
        self._current_floor_key = ""
        self._place_mode = ""
        self._surface_endpoint_snap_distance = self.DEFAULT_SURFACE_ENDPOINT_SNAP_DISTANCE
        self.current_map_path = ""
        self._placement_start = QPointF()
        self._surface_preview_line: QGraphicsLineItem | None = None
        self._surface_preview_rect: QGraphicsRectItem | None = None
        self._interaction_placement_points: list[QPointF] = []
        self._interaction_preview_lines: list[QGraphicsLineItem] = []
        self._interaction_preview_points: list[QGraphicsEllipseItem] = []

        self.setSceneRect(QRectF(0, 0, 4000, 4000))
        self.setBackgroundBrush(QBrush(canvas_background_color()))
        self._add_grid(4000, 4000)

    def load_map_image(self, path: str) -> bool:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return False

        if self._map_item is not None:
            self.removeItem(self._map_item)

        width = max(pixmap.width(), 1200)
        height = max(pixmap.height(), 800)
        self._reset_scene(width, height)
        self.current_map_path = path

        self._map_item = QGraphicsPixmapItem(pixmap)
        self._map_item.setZValue(-100)
        self._map_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.addItem(self._map_item)
        self._rebuild_interaction_items()
        return True

    def clear_map(self) -> None:
        self._reset_scene(4000, 4000)
        self._interactions = []
        self._surfaces = []
        self._current_floor_key = ""
        self._items_by_id.clear()
        self._surface_items.clear()
        self._place_mode = ""

    def set_floor(self, floor_key: str) -> None:
        self._current_floor_key = floor_key
        self._rebuild_surface_items()
        self._rebuild_interaction_items()

    def set_interactions(self, interactions: list[MapInteractionPoint]) -> None:
        self._interactions = deepcopy(interactions)
        self._rebuild_interaction_items()

    def set_surfaces(self, surfaces: list[MapSurface]) -> None:
        self._surfaces = deepcopy(surfaces)
        self._rebuild_surface_items()

    def set_place_mode(self, mode: str) -> None:
        self._place_mode = mode
        if mode != "interaction":
            self._clear_interaction_preview()
        if mode not in {"soft_wall", "hatch_surface"}:
            self._clear_surface_preview()
            self._placement_start = QPointF()
        debug_log(f"debug-scene: set_place_mode={mode!r}")

    def set_surface_endpoint_snap_distance(self, distance: float) -> None:
        self._surface_endpoint_snap_distance = max(0.0, float(distance))
        debug_log(f"debug-scene: set_surface_endpoint_snap_distance={self._surface_endpoint_snap_distance:.1f}")

    def surface_endpoint_snap_distance(self) -> float:
        return self._surface_endpoint_snap_distance

    def select_interaction(self, interaction_id: str | None) -> None:
        for item_id, item in self._items_by_id.items():
            item.setSelected(bool(interaction_id) and item_id == interaction_id)
        if interaction_id is None:
            self.clearSelection()

    def select_surface(self, surface_id: str | None) -> None:
        for item_id, item in self._surface_items.items():
            item.setSelected(bool(surface_id) and item_id == surface_id)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        debug_log(
            f"debug-scene: mousePress button={event.button()} mode={self._place_mode!r} "
            f"pos=({event.scenePos().x():.1f},{event.scenePos().y():.1f})"
        )
        if event.button() == Qt.MouseButton.LeftButton and self._place_mode == "interaction":
            item = self.itemAt(event.scenePos(), QTransform())
            debug_log(f"debug-scene: interaction item={type(item).__name__ if item else '-'}")
            if not isinstance(item, (MapInteractionItem, MapSurfaceItem)):
                self._append_interaction_point(event.scenePos())
                self._update_interaction_preview(event.scenePos())
                debug_log(
                    "debug-scene: interaction placement append "
                    f"count={len(self._interaction_placement_points)}"
                )
                event.accept()
                return
        if event.button() == Qt.MouseButton.RightButton and self._place_mode == "interaction":
            if self._interaction_placement_points:
                if len(self._interaction_placement_points) >= 2:
                    self._finish_interaction_placement()
                    debug_log("debug-scene: interaction placement finished by right click")
                else:
                    self._clear_interaction_preview()
                    debug_log("debug-scene: interaction placement canceled")
                event.accept()
                return

        if event.button() == Qt.MouseButton.LeftButton and self._place_mode in {"soft_wall", "hatch_surface"}:
            item = self.itemAt(event.scenePos(), QTransform())
            debug_log(f"debug-scene: surface item={type(item).__name__ if item else '-'}")
            if not isinstance(item, (MapInteractionItem, MapSurfaceItem)):
                self._placement_start = self._snap_surface_endpoint(event.scenePos())[0]
                debug_log(
                    f"debug-scene: placement start=({self._placement_start.x():.1f},{self._placement_start.y():.1f})"
                )
                self._update_surface_preview(event.scenePos())
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._place_mode == "interaction" and self._interaction_placement_points:
            self._update_interaction_preview(self._snap_interaction_point(event.scenePos()))
            event.accept()
            return
        if self._place_mode in {"soft_wall", "hatch_surface"} and not self._placement_start.isNull():
            debug_log(
                f"debug-scene: mouseMove pos=({event.scenePos().x():.1f},{event.scenePos().y():.1f})"
            )
            self._update_surface_preview(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        debug_log(
            f"debug-scene: mouseRelease button={event.button()} mode={self._place_mode!r} "
            f"start_null={self._placement_start.isNull()}"
        )
        if event.button() == Qt.MouseButton.LeftButton and self._place_mode in {"soft_wall", "hatch_surface"}:
            if not self._placement_start.isNull():
                start, end = self._calibrated_surface_points(self._placement_start, event.scenePos())
                debug_log(
                    f"debug-scene: calibrated start=({start.x():.1f},{start.y():.1f}) "
                    f"end=({end.x():.1f},{end.y():.1f}) len={(end - start).manhattanLength():.1f}"
                )
                self._clear_surface_preview()
                self._placement_start = QPointF()
                if (end - start).manhattanLength() >= 6:
                    self.surface_place_requested.emit(
                        self._place_mode,
                        start.x(),
                        start.y(),
                        end.x(),
                        end.y(),
                    )
                    debug_log("debug-scene: surface place emitted")
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._place_mode == "interaction":
            item = self.itemAt(event.scenePos(), QTransform())
            if not isinstance(item, (MapInteractionItem, MapSurfaceItem)):
                self._append_interaction_point(event.scenePos())
                self._finish_interaction_placement()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _reset_scene(self, width: int, height: int) -> None:
        self.clear()
        self._map_item = None
        self.current_map_path = ""
        self._items_by_id.clear()
        self._surface_items.clear()
        self._grid_items = []
        self._interaction_placement_points = []
        self._interaction_preview_lines = []
        self._interaction_preview_points = []
        self.setSceneRect(QRectF(0, 0, width, height))
        self.setBackgroundBrush(QBrush(canvas_background_color()))
        self._add_grid(width, height)

    def _rebuild_interaction_items(self) -> None:
        selected_ids = [item_id for item_id, item in self._items_by_id.items() if item.isSelected()]
        selected_id = selected_ids[0] if selected_ids else None

        for item in self._items_by_id.values():
            self.removeItem(item)
        self._items_by_id.clear()

        for interaction in self._interactions:
            if not self._is_visible_on_current_floor(interaction):
                continue
            item = MapInteractionItem(interaction, display_floor_key=self._current_floor_key)
            item.selected_id.connect(self.interaction_selected.emit)
            item.moved.connect(self.interaction_moved.emit)
            self.addItem(item)
            self._items_by_id[interaction.id] = item
            if interaction.id == selected_id:
                item.setSelected(True)

    def _rebuild_surface_items(self) -> None:
        selected_ids = [item_id for item_id, item in self._surface_items.items() if item.isSelected()]
        selected_id = selected_ids[0] if selected_ids else None

        for item in self._surface_items.values():
            self.removeItem(item)
        self._surface_items.clear()

        for surface in self._surfaces:
            if self._current_floor_key and surface.floor_key != self._current_floor_key:
                continue
            item = MapSurfaceItem(surface, editable=True)
            item.selected_id.connect(self.surface_selected.emit)
            item.moved.connect(self.surface_moved.emit)
            self.addItem(item)
            self._surface_items[surface.id] = item
            if surface.id == selected_id:
                item.setSelected(True)

    def _is_visible_on_current_floor(self, interaction: MapInteractionPoint) -> bool:
        if not self._current_floor_key:
            return True
        if interaction.floor_key == self._current_floor_key:
            return True
        return interaction.is_bidirectional and self._current_floor_key in interaction.linked_floor_keys

    def _add_grid(self, width: int, height: int) -> None:
        grid_pen = QPen(canvas_grid_color())
        grid_pen.setWidth(1)

        for x in range(0, width + 1, 100):
            item = self.addLine(x, 0, x, height, grid_pen)
            item.setZValue(-90)
            self._grid_items.append(item)

        for y in range(0, height + 1, 100):
            item = self.addLine(0, y, width, y, grid_pen)
            item.setZValue(-90)
            self._grid_items.append(item)

    def refresh_theme(self) -> None:
        self.setBackgroundBrush(QBrush(canvas_background_color()))
        grid_pen = QPen(canvas_grid_color())
        grid_pen.setWidth(1)
        for item in self._grid_items:
            item.setPen(grid_pen)
        for item in self._items_by_id.values():
            item.update()
        for item in self._surface_items.values():
            item.update()
        self.update()

    def _update_interaction_preview(self, cursor_point: QPointF) -> None:
        self._clear_interaction_preview_items()
        points = list(self._interaction_placement_points)
        if points:
            points = [QPointF(point) for point in points]
            points.append(self._snap_interaction_point(cursor_point))

        pen = QPen(canvas_grid_color())
        pen.setWidth(3)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        for start, end in zip(points, points[1:]):
            line_item = self.addLine(start.x(), start.y(), end.x(), end.y(), pen)
            line_item.setZValue(30)
            self._interaction_preview_lines.append(line_item)

        for point in self._interaction_placement_points:
            dot = self.addEllipse(point.x() - 6, point.y() - 6, 12, 12, pen, QBrush(canvas_grid_color()))
            dot.setZValue(31)
            self._interaction_preview_points.append(dot)

    def _clear_interaction_preview(self) -> None:
        self._clear_interaction_preview_items()
        self._interaction_placement_points = []

    def _append_interaction_point(self, raw_point: QPointF) -> None:
        point = self._snap_interaction_point(raw_point)
        if not self._interaction_placement_points:
            self._interaction_placement_points.append(point)
            return
        if self._distance(self._interaction_placement_points[-1], point) <= 2.0:
            return
        self._interaction_placement_points.append(point)

    def _finish_interaction_placement(self) -> None:
        if len(self._interaction_placement_points) >= 2:
            payload = [
                (current_point.x(), current_point.y())
                for current_point in self._interaction_placement_points
            ]
            self.interaction_place_requested.emit(payload)
            debug_log(
                "debug-scene: interaction place emitted "
                f"points={len(self._interaction_placement_points)}"
            )
        self._clear_interaction_preview()

    def _clear_interaction_preview_items(self) -> None:
        for item in self._interaction_preview_lines:
            self.removeItem(item)
        for item in self._interaction_preview_points:
            self.removeItem(item)
        self._interaction_preview_lines.clear()
        self._interaction_preview_points.clear()

    def _snap_interaction_point(self, point: QPointF) -> QPointF:
        if not self._interaction_placement_points:
            return QPointF(point)
        anchor = self._interaction_placement_points[-1]
        dx = point.x() - anchor.x()
        dy = point.y() - anchor.y()
        length = hypot(dx, dy)
        if length < 1e-6:
            return QPointF(anchor)
        angle = degrees(atan2(dy, dx))
        snapped_angle = round(angle / 45.0) * 45.0
        snapped_radian = radians(snapped_angle)
        return QPointF(
            anchor.x() + length * cos(snapped_radian),
            anchor.y() + length * sin(snapped_radian),
        )

    def _update_surface_preview(self, end: QPointF) -> None:
        self._clear_surface_preview()
        pen = QPen(canvas_grid_color())
        pen.setWidth(8 if self._place_mode == "soft_wall" else 3)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        start, calibrated_end = self._calibrated_surface_points(self._placement_start, end)
        if self._place_mode == "soft_wall":
            self._surface_preview_line = self.addLine(
                start.x(),
                start.y(),
                calibrated_end.x(),
                calibrated_end.y(),
                pen,
            )
            self._surface_preview_line.setZValue(30)
            return
        rect = QRectF(start, calibrated_end).normalized()
        self._surface_preview_rect = self.addRect(rect, pen)
        self._surface_preview_rect.setZValue(30)

    def _clear_surface_preview(self) -> None:
        if self._surface_preview_line is not None:
            self.removeItem(self._surface_preview_line)
            self._surface_preview_line = None
        if self._surface_preview_rect is not None:
            self.removeItem(self._surface_preview_rect)
            self._surface_preview_rect = None

    def _calibrated_surface_points(self, start: QPointF, raw_end: QPointF) -> tuple[QPointF, QPointF]:
        snapped_start, snapped_start_hit = self._snap_surface_endpoint(start)
        snapped_end, snapped_end_hit = self._snap_surface_endpoint(raw_end)
        if self._place_mode != "soft_wall":
            return snapped_start, snapped_end

        if snapped_end_hit is not None:
            return self._snap_segment_to_allowed_angle(snapped_end, raw_point=start, adjust_start=True)
        if snapped_start_hit is not None:
            return self._snap_segment_to_allowed_angle(snapped_start, raw_point=raw_end, adjust_start=False)

        dx = snapped_end.x() - snapped_start.x()
        dy = snapped_end.y() - snapped_start.y()
        length = hypot(dx, dy)
        if length < 1e-6:
            return snapped_start, snapped_end

        angle = degrees(atan2(dy, dx))
        snapped_angle = round(angle / 45.0) * 45.0
        snapped_radian = radians(snapped_angle)
        calibrated_end = QPointF(
            snapped_start.x() + length * cos(snapped_radian),
            snapped_start.y() + length * sin(snapped_radian),
        )
        calibrated_end, _ = self._snap_surface_endpoint(calibrated_end)
        return snapped_start, calibrated_end

    def _snap_segment_to_allowed_angle(
        self,
        fixed_point: QPointF,
        *,
        raw_point: QPointF,
        adjust_start: bool,
    ) -> tuple[QPointF, QPointF]:
        dx = raw_point.x() - fixed_point.x()
        dy = raw_point.y() - fixed_point.y()
        length = hypot(dx, dy)
        if length < 1e-6:
            return (raw_point, fixed_point) if adjust_start else (fixed_point, raw_point)

        angle = degrees(atan2(dy, dx))
        snapped_angle = round(angle / 45.0) * 45.0
        snapped_radian = radians(snapped_angle)
        adjusted_point = QPointF(
            fixed_point.x() + length * cos(snapped_radian),
            fixed_point.y() + length * sin(snapped_radian),
        )
        if adjust_start:
            return adjusted_point, fixed_point
        return fixed_point, adjusted_point

    def _snap_surface_endpoint(self, point: QPointF) -> tuple[QPointF, QPointF | None]:
        if not self._current_floor_key:
            return point, None

        best = point
        best_anchor = None
        best_distance = self._surface_endpoint_snap_distance
        for surface in self._surfaces:
            if surface.floor_key != self._current_floor_key:
                continue
            if surface.kind != MapSurfaceType.SOFT_WALL:
                continue
            for anchor in (
                QPointF(surface.start.x, surface.start.y),
                QPointF(surface.end.x, surface.end.y),
            ):
                distance = hypot(point.x() - anchor.x(), point.y() - anchor.y())
                if distance <= best_distance:
                    best = anchor
                    best_anchor = anchor
                    best_distance = distance
        return QPointF(best), best_anchor

    @staticmethod
    def _distance(first: QPointF, second: QPointF) -> float:
        return hypot(second.x() - first.x(), second.y() - first.y())
