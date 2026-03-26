from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from r6_tactics_board.domain.models import MapInteractionPoint, MapInteractionType


class MapInteractionItem(QGraphicsObject):
    selected_id = pyqtSignal(str)
    moved = pyqtSignal(str, float, float)

    def __init__(self, interaction: MapInteractionPoint) -> None:
        super().__init__()
        self.interaction = interaction
        self._radius = 12.0
        self._drag_start = QPointF()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(20)
        self.setPos(interaction.position.x, interaction.position.y)
        self.setToolTip(self._build_tooltip())

    def boundingRect(self) -> QRectF:  # noqa: N802
        size = self._radius * 2 + 6
        return QRectF(-size / 2, -size / 2, size, size)

    def paint(  # noqa: N802
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget

        fill = QColor("#3B82F6") if self.interaction.kind == MapInteractionType.STAIRS else QColor("#F97316")
        border = QColor("#FACC15") if self.isSelected() else QColor(255, 255, 255, 180)
        text = "S" if self.interaction.kind == MapInteractionType.STAIRS else "H"

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(border, 2))
        painter.setBrush(fill)
        painter.drawEllipse(QPointF(0, 0), self._radius, self._radius)

        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor("#0B1220"))
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, text)

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
        return (
            f"ID: {self.interaction.id}\n"
            f"Type: {self.interaction.kind.value}\n"
            f"Floor: {self.interaction.floor_key}\n"
            f"Linked: {linked}"
        )
