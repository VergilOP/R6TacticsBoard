from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene

from r6_tactics_board.domain.models import OperatorDisplayMode, OperatorState, Point2D, TeamSide
from r6_tactics_board.presentation.widgets.operator_item import OperatorItem


class MapScene(QGraphicsScene):
    operator_move_finished = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._map_item: QGraphicsPixmapItem | None = None
        self._operator_count = 0
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
        return True

    def clear_map(self) -> None:
        self._reset_scene(4000, 4000)

    def add_operator(self, position: QPointF | None = None) -> OperatorItem:
        self._operator_count += 1
        operator = OperatorItem(str(self._operator_count))
        operator.setZValue(10)

        if position is None:
            position = self.sceneRect().center()

        operator.setPos(position)
        self.addItem(operator)
        self.select_operator(operator)
        return operator

    def selected_operator(self) -> OperatorItem | None:
        for item in self.selectedItems():
            if isinstance(item, OperatorItem):
                return item
        return None

    def select_operator(self, operator: OperatorItem) -> None:
        self.clearSelection()
        operator.setSelected(True)

    def delete_selected_operator(self) -> bool:
        operator = self.selected_operator()
        if operator is None:
            return False

        self.removeItem(operator)
        return True

    def snapshot_operator_states(self) -> list[OperatorState]:
        states: list[OperatorState] = []

        for item in self.operator_items():
            display_mode = (
                OperatorDisplayMode.ICON
                if item.display_mode == OperatorItem.ICON
                else OperatorDisplayMode.CUSTOM_NAME
            )
            states.append(
                OperatorState(
                    id=item.operator_id,
                    operator_key=item.operator_key,
                    custom_name=item.custom_name,
                    side=TeamSide(item.side),
                    position=Point2D(x=item.pos().x(), y=item.pos().y()),
                    rotation=item.rotation(),
                    display_mode=display_mode,
                )
            )

        return sorted(states, key=lambda state: self._operator_sort_key(state.id))

    def snapshot_operator_states_dict(self) -> dict[str, OperatorState]:
        return {state.id: state for state in self.snapshot_operator_states()}

    def restore_operator_states(self, states: list[OperatorState]) -> None:
        self.sync_operator_states(states, select_operator_id=None)

    def sync_operator_states(
        self,
        states: list[OperatorState],
        select_operator_id: str | None = None,
    ) -> None:
        selected_id = select_operator_id
        if selected_id is None:
            current = self.selected_operator()
            selected_id = current.operator_id if current is not None else None

        existing = {item.operator_id: item for item in self.operator_items()}
        incoming_ids = {state.id for state in states}

        for operator_id, item in existing.items():
            if operator_id not in incoming_ids:
                self.removeItem(item)

        max_id = 0
        for state in states:
            operator = existing.get(state.id)
            if operator is None:
                operator = OperatorItem(state.id, state.custom_name)
                operator.setZValue(10)
                self.addItem(operator)

            operator.set_custom_name(state.custom_name)
            operator.set_side(state.side.value)
            operator.set_operator_key(state.operator_key)
            operator.set_display_mode(state.display_mode.value)
            operator.setRotation(state.rotation)
            operator.setPos(state.position.x, state.position.y)
            operator.setSelected(state.id == selected_id)
            max_id = max(max_id, self._operator_sort_key(state.id))

        if selected_id is None:
            self.clearSelection()

        self._operator_count = max_id

    def operator_items(self) -> list[OperatorItem]:
        items = [item for item in self.items() if isinstance(item, OperatorItem)]
        return sorted(items, key=lambda item: self._operator_sort_key(item.operator_id))

    def find_operator(self, operator_id: str) -> OperatorItem | None:
        for item in self.operator_items():
            if item.operator_id == operator_id:
                return item
        return None

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            operator = self.selected_operator()
            if operator is not None:
                self.operator_move_finished.emit(operator.operator_id)

    def _reset_scene(self, width: int, height: int) -> None:
        operators = [item for item in self.items() if isinstance(item, OperatorItem)]

        operator_states = [
            {
                "id": item.operator_id,
                "operator_key": item.operator_key,
                "custom_name": item.custom_name,
                "side": item.side,
                "display_mode": item.display_mode,
                "rotation": int(item.rotation()),
                "position": item.pos(),
            }
            for item in operators
        ]

        self.clear()
        self._map_item = None
        self.current_map_path = ""
        self.setSceneRect(QRectF(0, 0, width, height))
        self.setBackgroundBrush(QBrush(QColor("#202020")))
        self._add_grid(width, height)

        for state in operator_states:
            operator = OperatorItem(state["id"], state["custom_name"])
            operator.set_side(state["side"])
            operator.set_operator_key(state["operator_key"])
            operator.set_display_mode(state["display_mode"])
            operator.setRotation(state["rotation"])
            operator.setZValue(10)
            operator.setPos(state["position"])
            self.addItem(operator)

        self._operator_count = len(operator_states)

    def _add_grid(self, width: int, height: int) -> None:
        grid_pen = QPen(QColor("#2C2C2C"))
        grid_pen.setWidth(1)

        for x in range(0, width + 1, 100):
            self.addLine(x, 0, x, height, grid_pen)

        for y in range(0, height + 1, 100):
            self.addLine(0, y, width, y, grid_pen)

    @staticmethod
    def _operator_sort_key(operator_id: str) -> int:
        try:
            return int(operator_id)
        except ValueError:
            return 0
