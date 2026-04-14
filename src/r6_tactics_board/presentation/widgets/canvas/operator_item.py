from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
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
        self.show_icon = True
        self.show_name = False
        self.side = "attack"
        self.operator_key = ""
        self.floor_key = ""
        self.icon_pixmap = QPixmap()
        self.operator_scale = 1.0

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setTransformOriginPoint(0, 0)

    def boundingRect(self) -> QRectF:
        scale = self.operator_scale
        return QRectF(-16 * scale, -18 * scale, 32 * scale, 36 * scale)

    def shape(self) -> QPainterPath:
        scale = self.operator_scale
        path = QPainterPath()
        if self.show_icon:
            path.addEllipse(QRectF(-6 * scale, -6 * scale, 12 * scale, 12 * scale))
            triangle = QPolygonF(
                [
                    QPointF(0, -12 * scale),
                    QPointF(-3 * scale, -7 * scale),
                    QPointF(3 * scale, -7 * scale),
                ]
            )
            triangle_path = QPainterPath()
            triangle_path.addPolygon(triangle)
            path.addPath(triangle_path)
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.show_icon or self.show_name:
            self._paint_icon_mode(painter)

    def set_custom_name(self, name: str) -> None:
        self.custom_name = name.strip() or f"干员 {self.operator_id}"
        self.update()

    def set_display_mode(self, mode: str) -> None:
        if mode == self.CUSTOM_NAME:
            self.set_display_options(False, True)
        else:
            self.set_display_options(True, False)

    def set_display_options(self, show_icon: bool, show_name: bool) -> None:
        normalized_show_icon = bool(show_icon)
        normalized_show_name = bool(show_name)
        if not normalized_show_icon and not normalized_show_name:
            normalized_show_icon = True
        if (
            self.show_icon == normalized_show_icon
            and self.show_name == normalized_show_name
        ):
            return
        self.prepareGeometryChange()
        self.show_icon = normalized_show_icon
        self.show_name = normalized_show_name
        self.display_mode = (
            self.CUSTOM_NAME
            if self.show_name and not self.show_icon
            else self.ICON
        )
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

    def set_operator_scale(self, scale: float) -> None:
        normalized = max(0.4, min(2.5, scale))
        if abs(self.operator_scale - normalized) < 1e-6:
            return
        self.prepareGeometryChange()
        self.operator_scale = normalized
        self.update()

    def _paint_icon_mode(self, painter: QPainter) -> None:
        scale = self.operator_scale
        pen = QPen(operator_pen_color(self.isSelected()), 2)
        fill = operator_icon_fill_color(self.isSelected())
        if self.isSelected():
            pen.setWidth(3)

        triangle = QPolygonF(
            [
                QPointF(0, -12 * scale),
                QPointF(-3 * scale, -7 * scale),
                QPointF(3 * scale, -7 * scale),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(operator_arrow_color()))
        painter.drawPolygon(triangle)

        painter.save()
        painter.rotate(-self.rotation())
        painter.setPen(pen)
        icon_rect = QRectF(-6 * scale, -6 * scale, 12 * scale, 12 * scale)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(icon_rect)
        if self.show_icon and not self.icon_pixmap.isNull():
            painter.setBrush(QBrush(operator_icon_background_color()))
            painter.drawEllipse(icon_rect)
            clip_path = QPainterPath()
            clip_path.addEllipse(icon_rect)
            painter.save()
            painter.setClipPath(clip_path)
            painter.drawPixmap(icon_rect.toRect(), self.icon_pixmap)
            painter.restore()
        elif self.show_icon:
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(icon_rect)

        if self.show_name:
            painter.setPen(operator_text_color())
            painter.setFont(QFont("Microsoft YaHei UI", max(5, round(5 * scale))))
            painter.drawText(
                QRectF(-6 * scale, -4 * scale, 12 * scale, 8 * scale),
                int(Qt.AlignmentFlag.AlignCenter),
                self.operator_key[:2].upper() if self.operator_key else self.operator_id,
            )
        painter.restore()
