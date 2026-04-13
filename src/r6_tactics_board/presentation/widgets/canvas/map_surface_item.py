from math import hypot

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from r6_tactics_board.domain.models import MapSurface, MapSurfaceType, SurfaceOpeningType, TacticalSurfaceState
from r6_tactics_board.presentation.styles.theme import (
    surface_fill_brush_color,
    surface_hole_color,
    surface_label_color,
    surface_outline_color,
    surface_selection_color,
)


class MapSurfaceItem(QGraphicsObject):
    _marker_cache: dict[tuple[str, int, str, str, str], QPixmap] = {}

    selected_id = pyqtSignal(str)
    moved = pyqtSignal(str, float, float, float, float)

    def __init__(
        self,
        surface: MapSurface,
        *,
        editable: bool = False,
        state: TacticalSurfaceState | None = None,
    ) -> None:
        super().__init__()
        self.surface = surface
        self._editable = editable
        self._state = state
        self._drag_start_pos = QPointF()
        self._start_anchor = QPointF(surface.start.x, surface.start.y)
        self._end_anchor = QPointF(surface.end.x, surface.end.y)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, editable)
        self.setPos(0, 0)
        self.setZValue(12 if surface.kind == MapSurfaceType.SOFT_WALL else 11)
        self.setToolTip(self._build_tooltip())

    def set_surface_state(self, state: TacticalSurfaceState | None) -> None:
        self._state = state
        self.update()
        self.setToolTip(self._build_tooltip())

    def boundingRect(self) -> QRectF:  # noqa: N802
        rect = self.shape().boundingRect()
        if self.surface.kind == MapSurfaceType.SOFT_WALL:
            return rect.adjusted(-2.0, -2.0, 2.0, 2.0)
        return rect.adjusted(-3.0, -3.0, 3.0, 3.0)

    def shape(self) -> QPainterPath:  # noqa: N802
        if self.surface.kind == MapSurfaceType.SOFT_WALL:
            path = QPainterPath()
            path.moveTo(self._start_anchor)
            path.lineTo(self._end_anchor)
            stroker = QPainterPathStroker()
            stroker.setCapStyle(Qt.PenCapStyle.FlatCap)
            stroker.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            stroker.setWidth(12.0)
            return stroker.createStroke(path)

        rect = QRectF(self._start_anchor, self._end_anchor).normalized()
        if rect.width() < 12:
            rect.setWidth(12)
        if rect.height() < 12:
            rect.setHeight(12)
        path = QPainterPath()
        path.addRect(rect)
        return path

    def paint(  # noqa: N802
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.surface.kind == MapSurfaceType.SOFT_WALL:
            self._paint_soft_wall(painter)
        else:
            self._paint_hatch(painter)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._drag_start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if not self._editable:
            return
        if self.pos() != self._drag_start_pos:
            delta = self.pos() - self._drag_start_pos
            self._start_anchor += delta
            self._end_anchor += delta
            self.setPos(QPointF())
            self.moved.emit(
                self.surface.id,
                self._start_anchor.x(),
                self._start_anchor.y(),
                self._end_anchor.x(),
                self._end_anchor.y(),
            )

    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged and bool(value):
            self.selected_id.emit(self.surface.id)
        return super().itemChange(change, value)

    def _paint_soft_wall(self, painter: QPainter) -> None:
        is_selected = self.isSelected()
        reinforced = self._state.reinforced if self._state is not None else False
        path = QPainterPath()
        path.moveTo(self._start_anchor)
        path.lineTo(self._end_anchor)

        pen = QPen(surface_outline_color(self.surface.kind, reinforced, is_selected))
        pen.setWidth(12 if reinforced else 8)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.drawPath(path)

        inner_pen = QPen(surface_fill_brush_color(self.surface.kind, reinforced))
        inner_pen.setWidth(8 if reinforced else 5)
        inner_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(inner_pen)
        painter.drawPath(path)

        self._paint_surface_markers(painter)

    def _paint_hatch(self, painter: QPainter) -> None:
        rect = QRectF(self._start_anchor, self._end_anchor).normalized()
        if rect.width() < 12:
            rect.setWidth(12)
        if rect.height() < 12:
            rect.setHeight(12)

        reinforced = self._state.reinforced if self._state is not None else False
        is_selected = self.isSelected()
        painter.setPen(QPen(surface_outline_color(self.surface.kind, reinforced, is_selected), 3))
        painter.setBrush(QBrush(surface_fill_brush_color(self.surface.kind, reinforced)))
        painter.drawRect(rect)

        self._paint_surface_markers(painter, rect.center())

    def _paint_surface_markers(self, painter: QPainter, center: QPointF | None = None) -> None:
        if self._state is None or self.surface.kind != MapSurfaceType.SOFT_WALL:
            return

        center_point = center or QPointF(
            (self._start_anchor.x() + self._end_anchor.x()) / 2,
            (self._start_anchor.y() + self._end_anchor.y()) / 2,
        )
        if self._state.opening_type is not None:
            icon_map = {
                SurfaceOpeningType.PASSAGE: "passage",
                SurfaceOpeningType.CROUCH_PASSAGE: "crouch",
                SurfaceOpeningType.VAULT: "vault",
            }
            self._paint_marker_icon(painter, icon_map[self._state.opening_type], center_point)
            return

        markers: list[str] = []
        if self._state.foot_hole:
            markers.append("foot")
        if self._state.gun_hole:
            markers.append("gun")
        if not markers:
            return

        centers = self._marker_centers(center_point, len(markers))
        for marker, target in zip(markers, centers, strict=False):
            self._paint_marker_icon(painter, marker, target)

    def _marker_centers(self, center: QPointF, count: int) -> list[QPointF]:
        if count <= 1:
            return [center]

        if self.surface.kind == MapSurfaceType.SOFT_WALL:
            dx = self._end_anchor.x() - self._start_anchor.x()
            dy = self._end_anchor.y() - self._start_anchor.y()
            length = hypot(dx, dy)
            if length < 1e-6:
                normal = QPointF(0.0, -1.0)
            else:
                normal = QPointF(-dy / length, dx / length)
            spacing = 14.0
            return [
                QPointF(center.x() - normal.x() * spacing / 2, center.y() - normal.y() * spacing / 2),
                QPointF(center.x() + normal.x() * spacing / 2, center.y() + normal.y() * spacing / 2),
            ]

        spacing = 16.0
        return [
            QPointF(center.x() - spacing / 2, center.y()),
            QPointF(center.x() + spacing / 2, center.y()),
        ]

    def _paint_marker_icon(self, painter: QPainter, marker: str, center: QPointF) -> None:
        pixmap = self._marker_pixmap(marker, 22)
        target = QRectF(center.x() - pixmap.width() / 2, center.y() - pixmap.height() / 2, pixmap.width(), pixmap.height())
        painter.drawPixmap(target.toRect(), pixmap)

    def _marker_pixmap(self, marker: str, size: int) -> QPixmap:
        background = surface_hole_color().name()
        foreground = surface_label_color().name()
        accent = surface_selection_color().name()
        key = (marker, size, background, foreground, accent)
        cached = self._marker_cache.get(key)
        if cached is not None:
            return cached

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        badge_rect = QRectF(1.0, 1.0, size - 2.0, size - 2.0)
        painter.setPen(QPen(QColor(accent), 1.25))
        painter.setBrush(QBrush(QColor(background)))
        painter.drawRoundedRect(badge_rect, 6.0, 6.0)

        icon_pen = QPen(QColor(foreground), 2.0)
        icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        icon_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(icon_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if marker == "passage":
            painter.drawRoundedRect(QRectF(6.5, 4.5, 9.0, 13.0), 2.5, 2.5)
            painter.drawLine(QPointF(11.0, 8.0), QPointF(11.0, 17.0))
        elif marker == "crouch":
            painter.drawRoundedRect(QRectF(5.5, 9.0, 11.0, 7.0), 2.0, 2.0)
            painter.drawLine(QPointF(5.5, 8.0), QPointF(16.5, 8.0))
        elif marker == "vault":
            painter.drawRoundedRect(QRectF(5.5, 6.0, 11.0, 10.0), 2.0, 2.0)
            painter.drawLine(QPointF(5.5, 11.0), QPointF(16.5, 11.0))
            painter.drawLine(QPointF(11.0, 6.0), QPointF(11.0, 11.0))
        elif marker == "foot":
            painter.drawRoundedRect(QRectF(5.0, 11.0, 12.0, 4.0), 1.5, 1.5)
        elif marker == "gun":
            painter.drawEllipse(QRectF(7.0, 7.0, 8.0, 8.0))
            painter.drawLine(QPointF(11.0, 4.5), QPointF(11.0, 7.0))
            painter.drawLine(QPointF(11.0, 15.0), QPointF(11.0, 17.5))
            painter.drawLine(QPointF(4.5, 11.0), QPointF(7.0, 11.0))
            painter.drawLine(QPointF(15.0, 11.0), QPointF(17.5, 11.0))

        painter.end()
        self._marker_cache[key] = pixmap
        return pixmap

    def _build_tooltip(self) -> str:
        length = hypot(self._end_anchor.x() - self._start_anchor.x(), self._end_anchor.y() - self._start_anchor.y())
        opening = self._state.opening_type.value if self._state and self._state.opening_type else "-"
        return (
            f"ID: {self.surface.id}\n"
            f"Type: {self.surface.kind.value}\n"
            f"Floor: {self.surface.floor_key}\n"
            f"Length: {length:.1f}\n"
            f"Reinforced: {bool(self._state and self._state.reinforced)}\n"
            f"Opening: {opening}"
        )
