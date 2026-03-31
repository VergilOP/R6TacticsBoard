from collections.abc import Callable

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    Slider,
    SubtitleLabel,
)

from r6_tactics_board.domain.models import OperatorDisplayMode, OperatorTransitionMode
from r6_tactics_board.infrastructure.assets.asset_registry import MapFloorAsset
from r6_tactics_board.presentation.styles.theme import (
    card_stylesheet,
    floating_panel_stylesheet,
    popup_combo_stylesheet,
)
from r6_tactics_board.presentation.widgets.canvas.operator_item import OperatorItem


class PopupAwareComboBox(QComboBox):
    popupHidden = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._apply_theme()

    def hidePopup(self) -> None:  # noqa: N802
        super().hidePopup()
        self.popupHidden.emit()

    def _apply_theme(self) -> None:
        self.setStyleSheet(popup_combo_stylesheet())

    def refresh_theme(self) -> None:
        self._apply_theme()


class EditorPropertyPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("editor-property-panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.property_title = SubtitleLabel("属性面板")
        self.property_hint = BodyLabel("名称、阵营、图标是全局属性；位置、朝向、显示模式、楼层跟随当前时间点。")
        self.selection_label = BodyLabel("当前选中：无")
        self.keyframe_title = SubtitleLabel("关键帧属性")
        self.keyframe_hint = BodyLabel("关键帧名称和备注只作用于当前关键帧列。")

        self.keyframe_name_edit = LineEdit()
        self.keyframe_note_edit = LineEdit()
        self.name_edit = LineEdit()
        self.side_combo = ComboBox()
        self.operator_combo = ComboBox()
        self.rotation_slider = Slider(Qt.Orientation.Horizontal)
        self.rotation_value_label = BodyLabel("0°")
        self.floor_value_label = BodyLabel("-")
        self.display_mode_combo = ComboBox()
        self.transition_mode_combo = ComboBox()
        self.manual_interactions_edit = LineEdit()
        self.manual_interactions_hint = BodyLabel("手动互动点：留空时使用自动路径")
        self.manual_interaction_combo = PopupAwareComboBox()
        self.manual_interaction_add_button = PushButton("添加")
        self.manual_interaction_remove_button = PushButton("移除最后")
        self.manual_interaction_clear_button = PushButton("清空")
        self.manual_interactions_value_label = BodyLabel("自动路径")
        self.delete_operator_button = PushButton("删除选中干员")

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        property_grid = QGridLayout()
        property_grid.setHorizontalSpacing(12)
        property_grid.setVerticalSpacing(12)
        keyframe_grid = QGridLayout()
        keyframe_grid.setHorizontalSpacing(12)
        keyframe_grid.setVerticalSpacing(12)

        self.name_edit.setPlaceholderText("输入自定义名称")
        self.keyframe_name_edit.setPlaceholderText("例如：开局抢点")
        self.keyframe_note_edit.setPlaceholderText("例如：30 秒内优先控图")
        self.rotation_slider.setRange(0, 359)

        self.side_combo.addItem("进攻")
        self.side_combo.setItemData(0, "attack")
        self.side_combo.addItem("防守")
        self.side_combo.setItemData(1, "defense")

        self.display_mode_combo.addItem("干员图标")
        self.display_mode_combo.setItemData(0, OperatorItem.ICON)
        self.display_mode_combo.addItem("自定义名")
        self.display_mode_combo.setItemData(1, OperatorItem.CUSTOM_NAME)
        self.transition_mode_combo.addItem("自动路径")
        self.transition_mode_combo.setItemData(0, OperatorTransitionMode.AUTO.value)
        self.transition_mode_combo.addItem("手动互动点")
        self.transition_mode_combo.setItemData(1, OperatorTransitionMode.MANUAL.value)
        self.manual_interaction_combo.addItem("当前地图无可用互动点")
        self.manual_interaction_combo.setItemData(0, "")
        self.manual_interactions_edit.setPlaceholderText("例如：interaction-1, interaction-4")

        property_grid.addWidget(BodyLabel("名称"), 0, 0)
        property_grid.addWidget(self.name_edit, 0, 1)
        property_grid.addWidget(BodyLabel("阵营"), 1, 0)
        property_grid.addWidget(self.side_combo, 1, 1)
        property_grid.addWidget(BodyLabel("图标"), 2, 0)
        property_grid.addWidget(self.operator_combo, 2, 1)
        property_grid.addWidget(BodyLabel("朝向"), 3, 0)
        property_grid.addWidget(self.rotation_slider, 3, 1)
        property_grid.addWidget(BodyLabel("角度"), 4, 0)
        property_grid.addWidget(self.rotation_value_label, 4, 1)
        property_grid.addWidget(BodyLabel("显示模式"), 5, 0)
        property_grid.addWidget(self.display_mode_combo, 5, 1)
        property_grid.addWidget(BodyLabel("楼层"), 6, 0)
        property_grid.addWidget(self.floor_value_label, 6, 1)
        property_grid.addWidget(BodyLabel("路径模式"), 7, 0)
        property_grid.addWidget(self.transition_mode_combo, 7, 1)

        manual_selection_layout = QHBoxLayout()
        manual_selection_layout.setSpacing(8)
        manual_selection_layout.addWidget(self.manual_interaction_combo, 1)
        property_grid.addLayout(manual_selection_layout, 8, 1)
        property_grid.addWidget(BodyLabel("手动互动点"), 8, 0)

        self.manual_interactions_edit.hide()
        self.manual_interactions_value_label.hide()
        self.manual_interactions_hint.hide()

        keyframe_grid.addWidget(BodyLabel("名称"), 0, 0)
        keyframe_grid.addWidget(self.keyframe_name_edit, 0, 1)
        keyframe_grid.addWidget(BodyLabel("备注"), 1, 0)
        keyframe_grid.addWidget(self.keyframe_note_edit, 1, 1)

        layout.addWidget(self.property_title)
        layout.addWidget(self.property_hint)
        layout.addWidget(self.selection_label)
        layout.addLayout(property_grid)
        layout.addWidget(self.delete_operator_button)
        layout.addSpacing(12)
        layout.addWidget(self.keyframe_title)
        layout.addWidget(self.keyframe_hint)
        layout.addLayout(keyframe_grid)
        layout.addStretch(1)
        self._apply_theme()

    def refresh_theme(self) -> None:
        self._apply_theme()
        self.manual_interaction_combo.refresh_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(card_stylesheet(self.objectName()))


class FloorOverlayPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self.setObjectName("floor-panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_theme()
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(8)
        self.hide()

    def set_floors(
        self,
        floors: list[MapFloorAsset],
        current_floor_key: str,
        on_select: Callable[[str], None],
        *,
        multi_select: bool = False,
        selected_floor_keys: set[str] | None = None,
    ) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if len(floors) <= 1:
            self.hide()
            return

        self._layout.addWidget(BodyLabel("楼层"))
        for floor in floors:
            is_selected = (
                floor.key in (selected_floor_keys or set())
                if multi_select
                else floor.key == current_floor_key
            )
            button = PrimaryPushButton(floor.name) if is_selected else PushButton(floor.name)
            button.clicked.connect(lambda checked=False, key=floor.key: on_select(key))
            self._layout.addWidget(button)

        self.show()
        self.raise_()
        self.update()

    def reposition(self, map_rect: QRect) -> None:
        if self.isHidden():
            return
        self.layout().activate()
        self.setFixedSize(self.layout().sizeHint())
        x = map_rect.left() + 12
        y = max(map_rect.top() + 12, map_rect.top() + (map_rect.height() - self.height()) // 2)
        self.move(x, y)
        self.raise_()

    def _apply_theme(self) -> None:
        self.setStyleSheet(floating_panel_stylesheet("floor-panel"))

    def refresh_theme(self) -> None:
        self._apply_theme()


class PlaybackOverlayPanel(QWidget):
    def __init__(self, *, initial_duration_ms: int, parent=None) -> None:
        super().__init__(parent)

        self.previous_button = PushButton("上一项")
        self.play_button = PrimaryPushButton("播放")
        self.pause_button = PushButton("暂停")
        self.next_button = PushButton("下一项")
        self.progress_slider = Slider(Qt.Orientation.Horizontal)
        self.status_label = BodyLabel("未开始")
        self.speed_combo = ComboBox()
        self.duration_label = BodyLabel(f"过渡 {initial_duration_ms} ms")
        self.duration_slider = Slider(Qt.Orientation.Horizontal)

        self._init_ui(initial_duration_ms)

    def _init_ui(self, initial_duration_ms: int) -> None:
        layout = QHBoxLayout(self)
        self.setObjectName("playback-panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_theme()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.progress_slider.setRange(0, 0)
        self.progress_slider.setSingleStep(1)
        self.progress_slider.setPageStep(1)
        self.progress_slider.setMinimumWidth(260)
        self.duration_slider.setRange(200, 2000)
        self.duration_slider.setSingleStep(100)
        self.duration_slider.setPageStep(100)
        self.duration_slider.setValue(initial_duration_ms)
        self.duration_slider.setMaximumWidth(180)

        for index, (label, value) in enumerate((
            ("0.5x", 0.5),
            ("1.0x", 1.0),
            ("1.5x", 1.5),
            ("2.0x", 2.0),
        )):
            self.speed_combo.addItem(label)
            self.speed_combo.setItemData(index, value)
        self.speed_combo.setCurrentIndex(1)
        self.status_label.setFixedWidth(120)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.previous_button)
        self.pause_button.hide()
        layout.addWidget(self.play_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.progress_slider, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(BodyLabel("速度"))
        layout.addWidget(self.speed_combo)
        layout.addWidget(self.duration_label)
        layout.addWidget(self.duration_slider)

    def reposition(self, map_rect: QRect) -> None:
        self.layout().activate()
        self.setFixedSize(self.layout().sizeHint())
        x = map_rect.left() + max((map_rect.width() - self.width()) // 2, 12)
        y = map_rect.bottom() - self.height() - 12
        self.move(x, y)
        self.raise_()

    def _apply_theme(self) -> None:
        self.setStyleSheet(floating_panel_stylesheet("playback-panel"))

    def refresh_theme(self) -> None:
        self._apply_theme()
