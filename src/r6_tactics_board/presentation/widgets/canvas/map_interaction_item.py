from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from r6_tactics_board.domain.models import MapInteractionPoint, MapInteractionType
from r6_tactics_board.presentation.styles.theme import (
    interaction_badge_background_color,
    interaction_badge_border_color,
    interaction_badge_text_color,
    interaction_border_color,
    interaction_emphasis_ring_color,
    interaction_fill_color,
    interaction_hover_ring_color,
    interaction_text_color,
)


class MapInteractionItem(QGraphicsObject):
    selected_id = pyqtSignal(str)
    moved = pyqtSignal(str, float, float)

    def __init__(self, interaction: MapInteractionPoint, *, display_floor_key: str = "") -> None:
        super().__init__()
        self.interaction = interaction
        self._radius = 12.0
        self._drag_start = QPointF()
        self._sequence_index: int | None = None
        self._emphasized = False
        self._hovered = False
        self._display_floor_key = display_floor_key

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(20)
        self.setPos(interaction.position.x, interaction.position.y)
        self.setToolTip(self._build_tooltip())

    def boundingRect(self) -> QRectF:  # noqa: N802
        points = self._local_points()
        min_x = min(point.x() for point in points)
        max_x = max(point.x() for point in points)
        min_y = min(point.y() for point in points)
        max_y = max(point.y() for point in points)
        margin = self._radius + 16
        return QRectF(
            min_x - margin,
            min_y - margin,
            (max_x - min_x) + margin * 2,
            (max_y - min_y) + margin * 2,
        )

    def shape(self) -> QPainterPath:  # noqa: N802
        if not self._has_stair_path():
            path = QPainterPath()
            path.addEllipse(QPointF(0, 0), self._radius + 4, self._radius + 4)
            return path

        points = self._local_points()
        line_path = QPainterPath(points[0])
        for point in points[1:]:
            line_path.lineTo(point)
        stroker = QPainterPathStroker()
        stroker.setWidth(20)
        path = stroker.createStroke(line_path)
        path.addEllipse(points[0], self._radius + 4, self._radius + 4)
        path.addEllipse(points[-1], self._radius + 4, self._radius + 4)
        return path

    def set_preview_state(self, sequence_index: int | None, emphasized: bool, hovered: bool = False) -> None:
        self._sequence_index = sequence_index
        self._emphasized = emphasized
        self._hovered = hovered
        if emphasized:
            self.setZValue(26)
        elif hovered:
            self.setZValue(24)
        else:
            self.setZValue(20)
        self.update()

    def paint(  # noqa: N802
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._has_stair_path():
            self._paint_stair(painter)
        else:
            self._paint_point(painter)

        if self._sequence_index is not None:
            end_point = self._local_points()[-1]
            badge_rect = QRectF(end_point.x() + self._radius - 2, end_point.y() - self._radius - 8, 18, 18)
            painter.setPen(QPen(interaction_badge_border_color(), 1))
            painter.setBrush(interaction_badge_background_color())
            painter.drawEllipse(badge_rect)

            badge_font = QFont()
            badge_font.setBold(True)
            badge_font.setPointSize(8)
            painter.setFont(badge_font)
            painter.setPen(interaction_badge_text_color())
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(self._sequence_index + 1))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._drag_start = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if self.pos() != self._drag_start:
            self.moved.emit(self.interaction.id, self.pos().x(), self.pos().y())

    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged and bool(value):
            self.selected_id.emit(self.interaction.id)
        return super().itemChange(change, value)

    def _build_tooltip(self) -> str:
        linked = ", ".join(self.interaction.linked_floor_keys) if self.interaction.linked_floor_keys else "-"
        path_points = len(self.interaction.path_points)
        return (
            f"ID: {self.interaction.id}\n"
            f"Type: {self.interaction.kind.value}\n"
            f"Floor: {self.interaction.floor_key}\n"
            f"Linked: {linked}\n"
            f"Path points: {path_points}"
        )

    def _paint_point(self, painter: QPainter) -> None:
        fill = interaction_fill_color(self.interaction.kind)
        fill.setAlpha(240 if self._emphasized else 190)
        border = interaction_border_color(self.isSelected(), self._emphasized)
        text = "S" if self.interaction.kind == MapInteractionType.STAIRS else "H"

        if self._emphasized:
            painter.setPen(QPen(interaction_emphasis_ring_color(), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), self._radius + 6, self._radius + 6)
        elif self._hovered:
            painter.setPen(QPen(interaction_hover_ring_color(), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), self._radius + 5, self._radius + 5)

        painter.setPen(QPen(border, 2))
        painter.setBrush(fill)
        painter.drawEllipse(QPointF(0, 0), self._radius, self._radius)
        self._draw_center_text(painter, self.boundingRect(), text)

    def _paint_stair(self, painter: QPainter) -> None:
        points = self._local_points()
        if len(points) < 2:
            self._paint_point(painter)
            return

        outline_color = interaction_emphasis_ring_color() if self._emphasized else interaction_hover_ring_color()
        if self._emphasized or self._hovered:
            outline_pen = QPen(outline_color, 10)
            outline_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(outline_pen)
            for start, end in zip(points, points[1:]):
                painter.drawLine(start, end)

        line_pen = QPen(interaction_border_color(self.isSelected(), self._emphasized), 4)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line_pen)
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)

        start_fill = QColor(interaction_fill_color(self.interaction.kind))
        start_fill.setAlpha(235 if self._emphasized else 200)
        end_fill = QColor(start_fill)
        painter.setBrush(start_fill)
        painter.drawEllipse(points[0], self._radius, self._radius)
        painter.setBrush(end_fill)
        painter.drawEllipse(points[-1], self._radius, self._radius)

        self._draw_center_text(
            painter,
            QRectF(points[0].x() - self._radius, points[0].y() - self._radius, self._radius * 2, self._radius * 2),
            "↑",
        )
        self._draw_center_text(
            painter,
            QRectF(points[-1].x() - self._radius, points[-1].y() - self._radius, self._radius * 2, self._radius * 2),
            "↓",
        )

    def _draw_center_text(self, painter: QPainter, rect: QRectF, text: str) -> None:
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(interaction_text_color())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _local_points(self) -> list[QPointF]:
        if not self._has_stair_path():
            return [QPointF(0, 0)]

        absolute_points = [self.interaction.position]
        absolute_points.extend(self.interaction.path_points)
        absolute_points.append(self.interaction.target_position)
        origin = self.interaction.position
        return [
            QPointF(point.x - origin.x, point.y - origin.y)
            for point in absolute_points
        ]

    def _has_stair_path(self) -> bool:
        if self.interaction.kind != MapInteractionType.STAIRS or self.interaction.target_position is None:
            return False
        dx = self.interaction.target_position.x - self.interaction.position.x
        dy = self.interaction.target_position.y - self.interaction.position.y
        return abs(dx) > 0.5 or abs(dy) > 0.5 or bool(self.interaction.path_points)
