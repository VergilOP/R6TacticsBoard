from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem


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
        self.icon_pixmap = QPixmap()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setTransformOriginPoint(0, 0)

    def boundingRect(self) -> QRectF:
        return QRectF(-60, -36, 120, 72)

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

    def set_icon_path(self, path: str) -> None:
        self.icon_pixmap = QPixmap(path) if path else QPixmap()
        self.update()

    def _paint_icon_mode(self, painter: QPainter) -> None:
        pen = QPen(QColor("#F5F5F5"), 2)
        if self.isSelected():
            pen.setColor(QColor("#FFD54F"))
            pen.setWidth(3)

        painter.setPen(pen)
        icon_rect = QRectF(-24, -24, 48, 48)
        if not self.icon_pixmap.isNull():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(icon_rect)
            painter.drawPixmap(icon_rect.toRect(), self.icon_pixmap)
        else:
            painter.setBrush(QBrush(QColor("#2B88D8")))
            painter.drawEllipse(icon_rect)

        arrow = QPolygonF(
            [
                QPointF(0, -18),
                QPointF(-8, -4),
                QPointF(8, -4),
            ]
        )
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawPolygon(arrow)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        painter.drawText(
            QRectF(-20, 2, 40, 16),
            int(Qt.AlignmentFlag.AlignCenter),
            self.operator_key or self.operator_id,
        )

    def _paint_name_mode(self, painter: QPainter) -> None:
        pen = QPen(QColor("#F5F5F5"), 2)
        fill = QColor("#1F5E8C")
        if self.isSelected():
            pen.setColor(QColor("#FFD54F"))
            pen.setWidth(3)
            fill = QColor("#266E9F")

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
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawPolygon(arrow)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.drawText(
            QRectF(-46, -12, 92, 24),
            int(Qt.AlignmentFlag.AlignCenter),
            self.custom_name,
        )
