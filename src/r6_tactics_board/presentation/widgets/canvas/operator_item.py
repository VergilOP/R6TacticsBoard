from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem

from r6_tactics_board.presentation.styles.theme import (
    operator_arrow_color,
    operator_icon_background_color,
    operator_icon_fill_color,
    operator_name_fill_color,
    operator_name_text_color,
    operator_pen_color,
    operator_text_color,
)


class OperatorItem(QGraphicsItem):
    """Map operator item with direction indicator and icon/name display modes."""

    ICON = "icon"
    CUSTOM_NAME = "custom_name"

    def __init__(self, operator_id: str, custom_name: str = "") -> None:
        super().__init__()
        self.operator_id = operator_id
        self.custom_name = custom_name or f"干员 {operator_id}"
        self.display_mode = self.ICON
        self.side = "attack"
        self.operator_key = ""
        self.floor_key = ""
        self.icon_pixmap = QPixmap()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setTransformOriginPoint(0, 0)

    def boundingRect(self) -> QRectF:
        return QRectF(-15, -17, 30, 34)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.display_mode == self.CUSTOM_NAME:
            self._paint_name_mode(painter)
        else:
            self._paint_icon_mode(painter)

    def set_custom_name(self, name: str) -> None:
        self.custom_name = name.strip() or f"干员 {self.operator_id}"
        self.update()

    def set_display_mode(self, mode: str) -> None:
        self.display_mode = mode
        self.update()

    def set_side(self, side: str) -> None:
        self.side = side
        self.update()

    def set_operator_key(self, key: str) -> None:
        self.operator_key = key
        self.update()

    def set_floor_key(self, floor_key: str) -> None:
        self.floor_key = floor_key

    def set_icon_path(self, path: str) -> None:
        self.icon_pixmap = QPixmap(path) if path else QPixmap()
        self.update()

    def _paint_icon_mode(self, painter: QPainter) -> None:
        pen = QPen(operator_pen_color(self.isSelected()), 2)
        fill = operator_icon_fill_color(self.isSelected())
        if self.isSelected():
            pen.setWidth(3)

        triangle = QPolygonF(
            [
                QPointF(0, -12),
                QPointF(-3, -7),
                QPointF(3, -7),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(operator_arrow_color()))
        painter.drawPolygon(triangle)

        painter.save()
        painter.rotate(-self.rotation())
        painter.setPen(pen)
        icon_rect = QRectF(-6, -6, 12, 12)
        if not self.icon_pixmap.isNull():
            painter.setBrush(QBrush(operator_icon_background_color()))
            painter.drawEllipse(icon_rect)
            clip_path = QPainterPath()
            clip_path.addEllipse(icon_rect)
            painter.save()
            painter.setClipPath(clip_path)
            painter.drawPixmap(icon_rect.toRect(), self.icon_pixmap)
            painter.restore()
        else:
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(icon_rect)

        painter.setPen(operator_text_color())
        painter.setFont(QFont("Microsoft YaHei UI", 5))
        painter.drawText(
            QRectF(-6, -4, 12, 8),
            int(Qt.AlignmentFlag.AlignCenter),
            self.operator_key[:2].upper() if self.operator_key else self.operator_id,
        )
        painter.restore()

    def _paint_name_mode(self, painter: QPainter) -> None:
        pen = QPen(operator_pen_color(self.isSelected()), 2)
        fill = operator_name_fill_color(self.isSelected())
        if self.isSelected():
            pen.setWidth(3)

        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(QRectF(-52, -18, 104, 36), 10, 10)

        arrow = QPolygonF(
            [
                QPointF(0, -28),
                QPointF(-8, -14),
                QPointF(8, -14),
            ]
        )
        painter.setBrush(QBrush(operator_arrow_color()))
        painter.drawPolygon(arrow)

        painter.setPen(operator_name_text_color())
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.save()
        painter.rotate(-self.rotation())
        painter.drawText(
            QRectF(-46, -12, 92, 24),
            int(Qt.AlignmentFlag.AlignCenter),
            self.custom_name,
        )
        painter.restore()
