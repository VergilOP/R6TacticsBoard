from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
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

        fill = interaction_fill_color(self.interaction.kind)
        fill.setAlpha(240 if self._emphasized else 190)
        border = interaction_border_color(self.isSelected(), self._emphasized)
        text = "S" if self.interaction.kind == MapInteractionType.STAIRS else "H"

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
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

        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(interaction_text_color())
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, text)

        if self._sequence_index is not None:
            badge_rect = QRectF(self._radius - 2, -self._radius - 8, 18, 18)
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
        return (
            f"ID: {self.interaction.id}\n"
            f"Type: {self.interaction.kind.value}\n"
            f"Floor: {self.interaction.floor_key}\n"
            f"Linked: {linked}"
        )
