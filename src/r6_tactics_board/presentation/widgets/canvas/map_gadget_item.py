from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsItem


class MapGadgetItem(QGraphicsItem):
    def __init__(
        self,
        operator_id: str,
        gadget_key: str,
        icon_path: str,
        size: float = 24.0,
        item_kind: str = "gadget",
    ) -> None:
        super().__init__()
        self.operator_id = operator_id
        self.gadget_key = gadget_key
        self.item_kind = item_kind
        self._size = max(12.0, float(size))
        self._pixmap = QPixmap(icon_path) if icon_path else QPixmap()
        self._source_rect = self._effective_source_rect()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def boundingRect(self) -> QRectF:
        half = self._size / 2.0
        return QRectF(-half, -half, self._size, self._size)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        outline_pen = QPen(QColor(12, 12, 12, 220))
        outline_pen.setWidthF(1.5)
        painter.setPen(outline_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.75, 0.75, -0.75, -0.75), 4, 4)
        if not self._pixmap.isNull():
            source_width = self._source_rect.width()
            source_height = self._source_rect.height()
            if source_width > 0 and source_height > 0:
                content_rect = rect.adjusted(1.5, 1.5, -1.5, -1.5)
                scale = max(content_rect.width() / source_width, content_rect.height() / source_height)
                target_width = source_width * scale
                target_height = source_height * scale
                target = QRectF(
                    content_rect.center().x() - target_width / 2.0,
                    content_rect.center().y() - target_height / 2.0,
                    target_width,
                    target_height,
                )
                painter.save()
                painter.setClipRect(content_rect)
                painter.drawPixmap(target, self._pixmap, self._source_rect)
                painter.restore()

    def set_center(self, x: float, y: float) -> None:
        self.setPos(QPointF(x, y))

    def _effective_source_rect(self) -> QRectF:
        if self._pixmap.isNull():
            return QRectF()
        image = self._pixmap.toImage()
        if image.isNull():
            return QRectF(0.0, 0.0, float(self._pixmap.width()), float(self._pixmap.height()))

        left = image.width()
        top = image.height()
        right = -1
        bottom = -1

        for y in range(image.height()):
            for x in range(image.width()):
                if image.pixelColor(x, y).alpha() > 8:
                    left = min(left, x)
                    top = min(top, y)
                    right = max(right, x)
                    bottom = max(bottom, y)

        if right < left or bottom < top:
            return QRectF(0.0, 0.0, float(self._pixmap.width()), float(self._pixmap.height()))

        return QRectF(
            float(left),
            float(top),
            float(right - left + 1),
            float(bottom - top + 1),
        )
