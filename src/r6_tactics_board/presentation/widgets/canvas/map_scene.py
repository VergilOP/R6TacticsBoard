from copy import deepcopy
from math import atan2, degrees

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsPixmapItem, QGraphicsScene

from r6_tactics_board.domain.models import (
    MapInteractionPoint,
    MapSurface,
    OperatorDisplayMode,
    OperatorState,
    Point2D,
    TacticalSurfaceState,
    TeamSide,
)
from r6_tactics_board.presentation.styles.theme import (
    canvas_background_color,
    canvas_grid_color,
    preview_path_color,
    preview_route_color,
)
from r6_tactics_board.presentation.widgets.canvas.map_gadget_item import MapGadgetItem
from r6_tactics_board.presentation.widgets.canvas.map_interaction_item import MapInteractionItem
from r6_tactics_board.presentation.widgets.canvas.operator_item import OperatorItem
from r6_tactics_board.presentation.widgets.canvas.map_surface_item import MapSurfaceItem


class MapScene(QGraphicsScene):
    operator_transform_started = pyqtSignal()
    operator_move_finished = pyqtSignal(str)
    gadget_transform_started = pyqtSignal()
    gadget_move_finished = pyqtSignal(str, str, float, float, float, float, bool)
    gadget_placed = pyqtSignal(str, float, float)
    ability_transform_started = pyqtSignal()
    ability_move_finished = pyqtSignal(str, str, float, float, float, float, bool)
    ability_placed = pyqtSignal(str, float, float)
    surface_selected = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._map_item: QGraphicsPixmapItem | None = None
        self._operator_count = 0
        self.current_map_path = ""
        self._placement_state: OperatorState | None = None
        self._is_placing = False
        self._placement_operator_id = ""
        self._placement_anchor = QPointF()
        self._path_items: dict[str, QGraphicsLineItem] = {}
        self._grid_items: list[QGraphicsLineItem] = []
        self._interaction_items: dict[str, MapInteractionItem] = {}
        self._interaction_link_items: list[QGraphicsLineItem] = []
        self._interactions: list[MapInteractionPoint] = []
        self._interaction_floor_key = ""
        self._show_interactions = False
        self._highlighted_interaction_ids: set[str] = set()
        self._highlighted_interaction_order: list[str] = []
        self._hovered_interaction_id = ""
        self._surfaces: list[MapSurface] = []
        self._surface_states: dict[str, TacticalSurfaceState] = {}
        self._surface_items: dict[str, MapSurfaceItem] = {}
        self._gadget_items: list[MapGadgetItem] = []
        self._gadget_icon_paths: dict[tuple[str, str], str] = {}
        self._gadget_placement_operator_id = ""
        self._gadget_placement_key = ""
        self._gadget_placement_icon_path = ""
        self._gadget_placement_max_count = 0
        self._gadget_placement_positions: list[Point2D] = []
        self._gadget_placement_active = False
        self._ability_items: list[MapGadgetItem] = []
        self._ability_icon_paths: dict[tuple[str, str], str] = {}
        self._ability_placement_operator_id = ""
        self._ability_placement_key = ""
        self._ability_placement_icon_path = ""
        self._ability_placement_positions: list[Point2D] = []
        self._ability_placement_active = False
        self._dragging_gadget_item: MapGadgetItem | None = None
        self._dragging_gadget_start = QPointF()
        self._dragging_gadget_offset = QPointF()
        self._surface_floor_key = ""
        self._operator_scale = 1.0

        self.setSceneRect(QRectF(0, 0, 4000, 4000))
        self.setBackgroundBrush(QBrush(canvas_background_color()))

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
        self._rebuild_surface_items()
        self._rebuild_interaction_items()
        return True

    def clear_map(self) -> None:
        self._reset_scene(4000, 4000)

    def add_operator(self, position: QPointF | None = None) -> OperatorItem:
        self._operator_count += 1
        operator = OperatorItem(str(self._operator_count))
        operator.setZValue(10)
        operator.set_operator_scale(self._operator_scale)

        if position is None:
            position = self.sceneRect().center()

        operator.setPos(position)
        self.addItem(operator)
        self.select_operator(operator)
        return operator

    def set_placement_state(self, state: OperatorState | None) -> None:
        self._placement_state = deepcopy(state) if state is not None else None

    def set_gadget_catalog(self, icon_paths: dict[tuple[str, str], str]) -> None:
        self._gadget_icon_paths = dict(icon_paths)

    def set_ability_catalog(self, icon_paths: dict[tuple[str, str], str]) -> None:
        self._ability_icon_paths = dict(icon_paths)

    def set_gadget_placement(
        self,
        *,
        operator_id: str,
        gadget_key: str,
        icon_path: str,
        max_count: int,
        active: bool,
        positions: list[Point2D],
    ) -> None:
        self._gadget_placement_operator_id = operator_id
        self._gadget_placement_key = gadget_key
        self._gadget_placement_icon_path = icon_path
        self._gadget_placement_max_count = max(0, int(max_count))
        self._gadget_placement_active = bool(active and operator_id and gadget_key and icon_path)
        self._gadget_placement_positions = [Point2D(x=item.x, y=item.y) for item in positions]

    def set_ability_placement(
        self,
        *,
        operator_id: str,
        ability_key: str,
        icon_path: str,
        active: bool,
        positions: list[Point2D],
    ) -> None:
        self._ability_placement_operator_id = operator_id
        self._ability_placement_key = ability_key
        self._ability_placement_icon_path = icon_path
        self._ability_placement_active = bool(active and operator_id and ability_key and icon_path)
        self._ability_placement_positions = [Point2D(x=item.x, y=item.y) for item in positions]

    def set_interaction_overlays(
        self,
        interactions: list[MapInteractionPoint],
        floor_key: str,
        visible: bool,
        highlighted_ids: list[str] | None = None,
        hovered_id: str = "",
    ) -> None:
        self._interactions = list(interactions)
        self._interaction_floor_key = floor_key
        self._show_interactions = visible
        self._highlighted_interaction_order = list(highlighted_ids or [])
        self._highlighted_interaction_ids = set(highlighted_ids or [])
        self._hovered_interaction_id = hovered_id
        self._rebuild_interaction_items()

    def set_preview_paths(self, paths: dict[str, tuple[QPointF, QPointF]]) -> None:
        for item in self._path_items.values():
            self.removeItem(item)
        self._path_items.clear()

        dash_pen = QPen(preview_path_color())
        dash_pen.setStyle(Qt.PenStyle.DashLine)
        dash_pen.setWidth(2)

        for operator_id, (start, end) in paths.items():
            line_item = self.addLine(start.x(), start.y(), end.x(), end.y(), dash_pen)
            line_item.setZValue(4)
            self._path_items[operator_id] = line_item

    def set_surface_overlays(
        self,
        surfaces: list[MapSurface],
        surface_states: dict[str, TacticalSurfaceState],
        floor_key: str,
    ) -> None:
        self._surfaces = deepcopy(surfaces)
        self._surface_states = deepcopy(surface_states)
        self._surface_floor_key = floor_key
        self._rebuild_surface_items()

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

    def selected_surface(self) -> MapSurfaceItem | None:
        for item in self.selectedItems():
            if isinstance(item, MapSurfaceItem):
                return item
        return None

    def select_surface(self, surface_id: str | None) -> None:
        for item in self._surface_items.values():
            item.setSelected(bool(surface_id) and item.surface.id == surface_id)

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
                    gadget_key="",
                    rotation=item.rotation(),
                    display_mode=display_mode,
                    show_icon=item.show_icon,
                    show_name=item.show_name,
                    floor_key=item.floor_key,
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
            operator.set_floor_key(state.floor_key)
            operator.set_display_options(state.show_icon, state.show_name)
            operator.set_operator_scale(self._operator_scale)
            operator.setRotation(state.rotation)
            operator.setPos(state.position.x, state.position.y)
            operator.setSelected(state.id == selected_id)
            max_id = max(max_id, self._operator_sort_key(state.id))

        if selected_id is None:
            self.clearSelection()

        self._operator_count = max_id
        self._rebuild_gadget_items(states)
        self._rebuild_ability_items(states)

    def operator_items(self) -> list[OperatorItem]:
        items = [item for item in self.items() if isinstance(item, OperatorItem)]
        return sorted(items, key=lambda item: self._operator_sort_key(item.operator_id))

    def set_operator_scale(self, scale: float) -> None:
        self._operator_scale = max(0.4, min(2.5, scale))
        for item in self.operator_items():
            item.set_operator_scale(self._operator_scale)
        self.update()

    def find_operator(self, operator_id: str) -> OperatorItem | None:
        for item in self.operator_items():
            if item.operator_id == operator_id:
                return item
        return None

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._is_placing:
            self._update_placement_operator(event.scenePos())
            operator_id = self._placement_operator_id
            self._is_placing = False
            self._placement_operator_id = ""
            event.accept()
            if operator_id:
                self.operator_move_finished.emit(operator_id)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._dragging_gadget_item is not None:
            item = self._dragging_gadget_item
            start = QPointF(self._dragging_gadget_start)
            end = QPointF(item.pos())
            self._dragging_gadget_item = None
            self._dragging_gadget_offset = QPointF()
            item.setCursor(Qt.CursorShape.OpenHandCursor)
            delete_item = not self._token_drop_bounds().contains(end)
            if delete_item:
                self.removeItem(item)
                if item in self._gadget_items:
                    self._gadget_items.remove(item)
                if item in self._ability_items:
                    self._ability_items.remove(item)
            if delete_item or (start - end).manhattanLength() >= 0.1:
                if item.item_kind == "ability":
                    self.ability_move_finished.emit(
                        item.operator_id,
                        item.gadget_key,
                        start.x(),
                        start.y(),
                        end.x(),
                        end.y(),
                        delete_item,
                    )
                else:
                    self.gadget_move_finished.emit(
                        item.operator_id,
                        item.gadget_key,
                        start.x(),
                        start.y(),
                        end.x(),
                        end.y(),
                        delete_item,
                    )
            event.accept()
            return

        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            operator = self.selected_operator()
            if operator is not None:
                self.operator_move_finished.emit(operator.operator_id)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._gadget_placement_active:
            item = self._token_item_at(
                event.scenePos(),
                operator_id=self._gadget_placement_operator_id,
                token_key=self._gadget_placement_key,
                item_kind="gadget",
            )
            if (
                isinstance(item, MapGadgetItem)
                and item.item_kind == "gadget"
                and item.operator_id == self._gadget_placement_operator_id
                and item.gadget_key == self._gadget_placement_key
            ):
                self.clearSelection()
                self.gadget_transform_started.emit()
                self._dragging_gadget_item = item
                self._dragging_gadget_start = QPointF(item.pos())
                self._dragging_gadget_offset = item.pos() - event.scenePos()
                item.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

            if len(self._gadget_placement_positions) < self._gadget_placement_max_count:
                self.gadget_placed.emit(
                    self._gadget_placement_operator_id,
                    event.scenePos().x(),
                    event.scenePos().y(),
                )
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._ability_placement_active:
            item = self._token_item_at(
                event.scenePos(),
                operator_id=self._ability_placement_operator_id,
                token_key=self._ability_placement_key,
                item_kind="ability",
            )
            if (
                isinstance(item, MapGadgetItem)
                and item.item_kind == "ability"
                and item.operator_id == self._ability_placement_operator_id
                and item.gadget_key == self._ability_placement_key
            ):
                self.clearSelection()
                self.ability_transform_started.emit()
                self._dragging_gadget_item = item
                self._dragging_gadget_start = QPointF(item.pos())
                self._dragging_gadget_offset = item.pos() - event.scenePos()
                item.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

            self.ability_placed.emit(
                self._ability_placement_operator_id,
                event.scenePos().x(),
                event.scenePos().y(),
            )
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._placement_state is not None:
            self.operator_transform_started.emit()
            self._is_placing = True
            self._placement_anchor = event.scenePos()
            operator = self._ensure_operator_from_placement_state()
            self._placement_operator_id = operator.operator_id
            self.select_operator(operator)
            self._update_placement_operator(event.scenePos())
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.scenePos(), QTransform())
            if isinstance(item, MapGadgetItem):
                self.gadget_transform_started.emit()
                self._dragging_gadget_item = item
                self._dragging_gadget_start = QPointF(item.pos())
            if isinstance(item, OperatorItem):
                self.operator_transform_started.emit()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging_gadget_item is not None:
            self._dragging_gadget_item.setPos(event.scenePos() + self._dragging_gadget_offset)
            event.accept()
            return

        if self._is_placing:
            self._update_placement_operator(event.scenePos())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def _reset_scene(self, width: int, height: int) -> None:
        operators = [item for item in self.items() if isinstance(item, OperatorItem)]

        operator_states = [
            {
                "id": item.operator_id,
                "operator_key": item.operator_key,
                "custom_name": item.custom_name,
                "side": item.side,
                "floor_key": item.floor_key,
                "display_mode": item.display_mode,
                "show_icon": item.show_icon,
                "show_name": item.show_name,
                "rotation": int(item.rotation()),
                "position": item.pos(),
            }
            for item in operators
        ]

        self.clear()
        self._map_item = None
        self.current_map_path = ""
        self._path_items = {}
        self._grid_items = []
        self._surface_items = {}
        self._gadget_items = []
        self._ability_items = []
        self._interaction_items = {}
        self._interaction_link_items = []
        self.setSceneRect(QRectF(0, 0, width, height))
        self.setBackgroundBrush(QBrush(canvas_background_color()))
        self._add_grid(width, height)

        for state in operator_states:
            operator = OperatorItem(state["id"], state["custom_name"])
            operator.set_side(state["side"])
            operator.set_operator_key(state["operator_key"])
            operator.set_floor_key(state["floor_key"])
            operator.set_display_options(state["show_icon"], state["show_name"])
            operator.set_operator_scale(self._operator_scale)
            operator.setRotation(state["rotation"])
            operator.setZValue(10)
            operator.setPos(state["position"])
            self.addItem(operator)

        self._operator_count = len(operator_states)

    def _add_grid(self, width: int, height: int) -> None:
        grid_pen = QPen(canvas_grid_color())
        grid_pen.setWidth(1)

        for x in range(0, width + 1, 100):
            item = self.addLine(x, 0, x, height, grid_pen)
            item.setZValue(-90)
            self._grid_items.append(item)

        for y in range(0, height + 1, 100):
            item = self.addLine(0, y, width, y, grid_pen)
            item.setZValue(-90)
            self._grid_items.append(item)

    @staticmethod
    def _operator_sort_key(operator_id: str) -> int:
        try:
            return int(operator_id)
        except ValueError:
            return 0

    def _ensure_operator_from_placement_state(self) -> OperatorItem:
        assert self._placement_state is not None

        operator = self.find_operator(self._placement_state.id)
        if operator is None:
            operator = OperatorItem(self._placement_state.id, self._placement_state.custom_name)
            operator.setZValue(10)
            self.addItem(operator)

        operator.set_custom_name(self._placement_state.custom_name)
        operator.set_side(self._placement_state.side.value)
        operator.set_operator_key(self._placement_state.operator_key)
        operator.set_floor_key(self._placement_state.floor_key)
        operator.set_display_options(self._placement_state.show_icon, self._placement_state.show_name)
        operator.set_operator_scale(self._operator_scale)
        operator.setPos(self._placement_anchor)
        operator.setRotation(self._placement_state.rotation)
        self._operator_count = max(self._operator_count, self._operator_sort_key(operator.operator_id))
        return operator

    def _update_placement_operator(self, scene_pos: QPointF) -> None:
        if not self._placement_operator_id:
            return

        operator = self.find_operator(self._placement_operator_id)
        if operator is None:
            return

        operator.setPos(self._placement_anchor)
        delta = scene_pos - self._placement_anchor
        if delta.manhattanLength() >= 1:
            operator.setRotation(degrees(atan2(delta.y(), delta.x())) + 90)

    def _rebuild_interaction_items(self) -> None:
        for line_item in self._interaction_link_items:
            self.removeItem(line_item)
        self._interaction_link_items.clear()
        for item in self._interaction_items.values():
            self.removeItem(item)
        self._interaction_items.clear()

        if not self._show_interactions:
            return

        sequence_index_by_id = {
            interaction_id: index
            for index, interaction_id in enumerate(self._highlighted_interaction_order)
        }

        for interaction in self._interactions:
            if not self._interaction_visible(interaction):
                continue

            item = MapInteractionItem(interaction, display_floor_key=self._interaction_floor_key)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.addItem(item)
            if interaction.id in self._highlighted_interaction_ids:
                sequence_index = sequence_index_by_id[interaction.id]
                item.set_preview_state(
                    sequence_index,
                    True,
                    hovered=interaction.id == self._hovered_interaction_id,
                )
            else:
                item.set_preview_state(None, False, hovered=interaction.id == self._hovered_interaction_id)
            self._interaction_items[interaction.id] = item

        ordered_items = [
            self._interaction_items[item_id]
            for item_id in self._highlighted_interaction_order
            if item_id in self._interaction_items
        ]
        if len(ordered_items) >= 2:
            route_pen = QPen(preview_route_color())
            route_pen.setWidth(2)
            route_pen.setStyle(Qt.PenStyle.DashLine)
            for start_item, end_item in zip(ordered_items, ordered_items[1:]):
                line_item = self.addLine(
                    start_item.pos().x(),
                    start_item.pos().y(),
                    end_item.pos().x(),
                    end_item.pos().y(),
                    route_pen,
                )
                line_item.setZValue(18)
            self._interaction_link_items.append(line_item)

    def _rebuild_surface_items(self) -> None:
        selected_ids = [item_id for item_id, item in self._surface_items.items() if item.isSelected()]
        selected_id = selected_ids[0] if selected_ids else None
        for item in self._surface_items.values():
            self.removeItem(item)
        self._surface_items.clear()

        for surface in self._surfaces:
            if self._surface_floor_key and surface.floor_key != self._surface_floor_key:
                continue
            item = MapSurfaceItem(
                surface,
                editable=False,
                state=self._surface_states.get(surface.id),
            )
            item.selected_id.connect(self.surface_selected.emit)
            self.addItem(item)
            self._surface_items[surface.id] = item
            if surface.id == selected_id:
                item.setSelected(True)

    def _rebuild_gadget_items(self, states: list[OperatorState]) -> None:
        for item in self._gadget_items:
            self.removeItem(item)
        self._gadget_items.clear()

        current_floor = self._surface_floor_key or self._interaction_floor_key
        for state in states:
            if not state.gadget_key or not state.gadget_positions:
                continue
            if current_floor and state.floor_key and state.floor_key != current_floor:
                continue
            icon_path = self._gadget_icon_paths.get((state.side.value, state.gadget_key), "")
            if not icon_path:
                continue
            for point in state.gadget_positions:
                item = MapGadgetItem(state.id, state.gadget_key, icon_path, item_kind="gadget")
                item.set_center(point.x, point.y)
                item.setZValue(30)
                self.addItem(item)
                self._gadget_items.append(item)

    def _rebuild_ability_items(self, states: list[OperatorState]) -> None:
        for item in self._ability_items:
            self.removeItem(item)
        self._ability_items.clear()

        current_floor = self._surface_floor_key or self._interaction_floor_key
        for state in states:
            if not state.operator_key or not state.ability_positions:
                continue
            if current_floor and state.floor_key and state.floor_key != current_floor:
                continue
            icon_path = self._ability_icon_paths.get((state.side.value, state.operator_key), "")
            if not icon_path:
                continue
            for point in state.ability_positions:
                item = MapGadgetItem(state.id, state.operator_key, icon_path, item_kind="ability")
                item.set_center(point.x, point.y)
                item.setZValue(30)
                self.addItem(item)
                self._ability_items.append(item)

    def _token_drop_bounds(self) -> QRectF:
        if self._map_item is not None:
            return self._map_item.sceneBoundingRect()
        return self.sceneRect()

    def _token_item_at(
        self,
        scene_pos: QPointF,
        *,
        operator_id: str,
        token_key: str,
        item_kind: str,
    ) -> MapGadgetItem | None:
        if not operator_id or not token_key:
            return None

        for item in self.items(scene_pos):
            if not isinstance(item, MapGadgetItem):
                continue
            if item.item_kind != item_kind:
                continue
            if item.operator_id != operator_id or item.gadget_key != token_key:
                continue
            local_pos = item.mapFromScene(scene_pos)
            if item.shape().contains(local_pos):
                return item
        return None

    def _interaction_visible(self, interaction: MapInteractionPoint) -> bool:
        if not self._interaction_floor_key:
            return True
        if interaction.floor_key == self._interaction_floor_key:
            return True
        return interaction.is_bidirectional and self._interaction_floor_key in interaction.linked_floor_keys

    def refresh_theme(self) -> None:
        self.setBackgroundBrush(QBrush(canvas_background_color()))

        grid_pen = QPen(canvas_grid_color())
        grid_pen.setWidth(1)
        for item in self._grid_items:
            item.setPen(grid_pen)

        path_pen = QPen(preview_path_color())
        path_pen.setStyle(Qt.PenStyle.DashLine)
        path_pen.setWidth(2)
        for item in self._path_items.values():
            item.setPen(path_pen)

        route_pen = QPen(preview_route_color())
        route_pen.setWidth(2)
        route_pen.setStyle(Qt.PenStyle.DashLine)
        for item in self._interaction_link_items:
            item.setPen(route_pen)

        for operator in self.operator_items():
            operator.update()
        for interaction in self._interaction_items.values():
            interaction.update()
        for surface in self._surface_items.values():
            surface.update()
        self.update()
