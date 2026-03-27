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
        self._sequence_index: int | None = None
        self._emphasized = False
        self._hovered = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(20)
        self.setPos(interaction.position.x, interaction.position.y)
        self.setToolTip(self._build_tooltip())

    def boundingRect(self) -> QRectF:  # noqa: N802
        size = self._radius * 2 + 24
        return QRectF(-size / 2, -size / 2, size, size)

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

        fill = QColor("#3B82F6") if self.interaction.kind == MapInteractionType.STAIRS else QColor("#F97316")
        fill.setAlpha(240 if self._emphasized else 190)
        border = QColor("#FACC15") if (self.isSelected() or self._emphasized) else QColor(255, 255, 255, 140)
        text = "S" if self.interaction.kind == MapInteractionType.STAIRS else "H"

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._emphasized:
            painter.setPen(QPen(QColor(250, 204, 21, 190), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), self._radius + 6, self._radius + 6)
        elif self._hovered:
            painter.setPen(QPen(QColor(96, 165, 250, 190), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), self._radius + 5, self._radius + 5)
        painter.setPen(QPen(border, 2))
        painter.setBrush(fill)
        painter.drawEllipse(QPointF(0, 0), self._radius, self._radius)

        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor("#0B1220"))
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, text)

        if self._sequence_index is not None:
            badge_rect = QRectF(self._radius - 2, -self._radius - 8, 18, 18)
            painter.setPen(QPen(QColor("#FFF7CC"), 1))
            painter.setBrush(QColor("#111827"))
            painter.drawEllipse(badge_rect)

            badge_font = QFont()
            badge_font.setBold(True)
            badge_font.setPointSize(8)
            painter.setFont(badge_font)
            painter.setPen(QColor("#FACC15"))
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
        return (
            f"ID: {self.interaction.id}\n"
            f"Type: {self.interaction.kind.value}\n"
            f"Floor: {self.interaction.floor_key}\n"
            f"Linked: {linked}"
        )
