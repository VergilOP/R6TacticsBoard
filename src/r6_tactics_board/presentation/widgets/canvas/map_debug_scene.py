from copy import deepcopy

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene

from r6_tactics_board.domain.models import MapInteractionPoint
from r6_tactics_board.presentation.widgets.canvas.map_interaction_item import MapInteractionItem


class MapDebugScene(QGraphicsScene):
    interaction_selected = pyqtSignal(str)
    interaction_moved = pyqtSignal(str, float, float)
    interaction_place_requested = pyqtSignal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self._map_item: QGraphicsPixmapItem | None = None
        self._items_by_id: dict[str, MapInteractionItem] = {}
        self._interactions: list[MapInteractionPoint] = []
        self._current_floor_key = ""
        self._place_mode = False
        self.current_map_path = ""

        self.setSceneRect(QRectF(0, 0, 4000, 4000))
        self.setBackgroundBrush(QBrush(QColor("#202020")))
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
        self._current_floor_key = ""
        self._items_by_id.clear()
        self._place_mode = False

    def set_floor(self, floor_key: str) -> None:
        self._current_floor_key = floor_key
        self._rebuild_interaction_items()

    def set_interactions(self, interactions: list[MapInteractionPoint]) -> None:
        self._interactions = deepcopy(interactions)
        self._rebuild_interaction_items()

    def set_place_mode(self, enabled: bool) -> None:
        self._place_mode = enabled

    def select_interaction(self, interaction_id: str | None) -> None:
        for item_id, item in self._items_by_id.items():
            item.setSelected(bool(interaction_id) and item_id == interaction_id)
        if interaction_id is None:
            self.clearSelection()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._place_mode:
            item = self.itemAt(event.scenePos(), QTransform())
            if not isinstance(item, MapInteractionItem):
                self.interaction_place_requested.emit(event.scenePos().x(), event.scenePos().y())
                event.accept()
                return

        super().mousePressEvent(event)

    def _reset_scene(self, width: int, height: int) -> None:
        self.clear()
        self._map_item = None
        self.current_map_path = ""
        self._items_by_id.clear()
        self.setSceneRect(QRectF(0, 0, width, height))
        self.setBackgroundBrush(QBrush(QColor("#202020")))
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
            item = MapInteractionItem(interaction)
            item.selected_id.connect(self.interaction_selected.emit)
            item.moved.connect(self.interaction_moved.emit)
            self.addItem(item)
            self._items_by_id[interaction.id] = item
            if interaction.id == selected_id:
                item.setSelected(True)

    def _is_visible_on_current_floor(self, interaction: MapInteractionPoint) -> bool:
        if not self._current_floor_key:
            return True
        if interaction.floor_key == self._current_floor_key:
            return True
        return interaction.is_bidirectional and self._current_floor_key in interaction.linked_floor_keys

    def _add_grid(self, width: int, height: int) -> None:
        grid_pen = QPen(QColor("#2C2C2C"))
        grid_pen.setWidth(1)

        for x in range(0, width + 1, 100):
            self.addLine(x, 0, x, height, grid_pen)

        for y in range(0, height + 1, 100):
            self.addLine(0, y, width, y, grid_pen)
