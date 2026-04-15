from collections.abc import Callable

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QTabWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    Slider,
    SubtitleLabel,
)

from r6_tactics_board.domain.models import OperatorTransitionMode, SurfaceOpeningType
from r6_tactics_board.infrastructure.assets.asset_registry import MapFloorAsset
from r6_tactics_board.presentation.styles.theme import (
    floating_panel_stylesheet,
    popup_combo_stylesheet,
    subtle_danger_button_stylesheet,
    tab_widget_stylesheet,
)


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
        self._active_section = "operator"

        self.property_title = SubtitleLabel("属性面板")
        self.property_hint = BodyLabel("名称、阵营、图标是全局属性；位置、朝向、显示与楼层属于当前时间点。")
        self.selection_label = BodyLabel("当前选中：无")
        self.keyframe_title = SubtitleLabel("关键帧")
        self.keyframe_hint = BodyLabel("当前关键帧：-")
        self.surface_title = SubtitleLabel("装修")
        self.surface_hint = BodyLabel("加固总数上限为 10；大洞三选一，且不能与脚洞、对枪洞并存。")
        self.surface_selection_label = BodyLabel("当前装修：无")
        self.surface_count_label = BodyLabel("加固数量：0 / 10")

        self.keyframe_name_edit = LineEdit()
        self.keyframe_note_edit = LineEdit()
        self.name_edit = LineEdit()
        self.side_combo = ComboBox()
        self.operator_combo = ComboBox()
        self.rotation_slider = Slider(Qt.Orientation.Horizontal)
        self.rotation_value_label = BodyLabel("0°")
        self.floor_value_label = BodyLabel("-")
        self.gadget_label = BodyLabel("道具")
        self.gadget_combo = ComboBox()
        self.gadget_count_label = BodyLabel("-")
        self.place_gadget_button = PushButton("放置道具")
        self.clear_gadget_button = PushButton("清空当前帧道具")
        self.ability_label = BodyLabel("技能")
        self.ability_name_label = BodyLabel("-")
        self.ability_count_label = BodyLabel("-")
        self.place_ability_button = PushButton("放置技能")
        self.clear_ability_button = PushButton("清空当前帧技能")
        self.transition_mode_label = BodyLabel("路径模式")
        self.manual_interaction_label = BodyLabel("手动互动点")
        self.show_icon_box = QCheckBox("显示图标")
        self.show_name_box = QCheckBox("显示名字")
        self.operator_size_slider = Slider(Qt.Orientation.Horizontal)
        self.operator_size_value_label = BodyLabel("100%")
        self.transition_mode_combo = ComboBox()
        self.manual_interactions_hint = BodyLabel("")
        self.manual_interaction_combo = PopupAwareComboBox()
        self.delete_operator_button = PushButton("删除选中干员")

        self.reinforce_button = PushButton("加固")
        self.surface_opening_label = BodyLabel("开洞")
        self.opening_combo = ComboBox()
        self.foot_hole_box = QCheckBox("脚洞")
        self.gun_hole_box = QCheckBox("对枪洞")

        self.section_tabs = QTabWidget()
        self.operator_page = QWidget()
        self.surface_page = QWidget()
        self.keyframe_page = QWidget()

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        property_grid = QGridLayout()
        property_grid.setHorizontalSpacing(12)
        property_grid.setVerticalSpacing(12)
        keyframe_grid = QGridLayout()
        keyframe_grid.setHorizontalSpacing(12)
        keyframe_grid.setVerticalSpacing(12)
        surface_grid = QGridLayout()
        surface_grid.setHorizontalSpacing(12)
        surface_grid.setVerticalSpacing(12)

        self.name_edit.setPlaceholderText("输入自定义名称")
        self.keyframe_name_edit.setPlaceholderText("例如：默认站位")
        self.keyframe_note_edit.setPlaceholderText("例如：10 秒内优先控图")
        self.rotation_slider.setRange(0, 359)
        self.operator_size_slider.setRange(50, 160)
        self.operator_size_slider.setValue(100)
        self.place_gadget_button.setCheckable(True)
        self.place_ability_button.setCheckable(True)

        self.side_combo.addItem("进攻")
        self.side_combo.setItemData(0, "attack")
        self.side_combo.addItem("防守")
        self.side_combo.setItemData(1, "defense")

        self.transition_mode_combo.addItem("自动路径")
        self.transition_mode_combo.setItemData(0, OperatorTransitionMode.AUTO.value)
        self.transition_mode_combo.addItem("手动互动点")
        self.transition_mode_combo.setItemData(1, OperatorTransitionMode.MANUAL.value)
        self.gadget_combo.addItem("无")
        self.gadget_combo.setItemData(0, "")
        self.manual_interaction_combo.addItem("当前地图无可用互动点")
        self.manual_interaction_combo.setItemData(0, "")

        self.opening_combo.addItem("无")
        self.opening_combo.setItemData(0, "")
        self.opening_combo.addItem("过人洞")
        self.opening_combo.setItemData(1, SurfaceOpeningType.PASSAGE.value)
        self.opening_combo.addItem("蹲姿过人洞")
        self.opening_combo.setItemData(2, SurfaceOpeningType.CROUCH_PASSAGE.value)
        self.opening_combo.addItem("翻越洞")
        self.opening_combo.setItemData(3, SurfaceOpeningType.VAULT.value)

        display_layout = QHBoxLayout()
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(8)
        display_layout.addWidget(self.show_icon_box)
        display_layout.addWidget(self.show_name_box)
        display_layout.addStretch(1)

        size_layout = QHBoxLayout()
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(8)
        size_layout.addWidget(self.operator_size_slider, 1)
        size_layout.addWidget(self.operator_size_value_label)

        gadget_layout = QHBoxLayout()
        gadget_layout.setContentsMargins(0, 0, 0, 0)
        gadget_layout.setSpacing(8)
        gadget_layout.addWidget(self.gadget_combo, 1)
        gadget_layout.addWidget(self.place_gadget_button)
        gadget_layout.addWidget(self.clear_gadget_button)

        ability_layout = QHBoxLayout()
        ability_layout.setContentsMargins(0, 0, 0, 0)
        ability_layout.setSpacing(8)
        ability_layout.addWidget(self.ability_count_label, 1)
        ability_layout.addWidget(self.place_ability_button)
        ability_layout.addWidget(self.clear_ability_button)

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
        property_grid.addWidget(self.gadget_label, 5, 0)
        property_grid.addLayout(gadget_layout, 5, 1)
        property_grid.addWidget(BodyLabel("数量"), 6, 0)
        property_grid.addWidget(self.gadget_count_label, 6, 1)
        property_grid.addWidget(self.ability_label, 7, 0)
        property_grid.addWidget(self.ability_name_label, 7, 1)
        property_grid.addWidget(BodyLabel("技能数量"), 8, 0)
        property_grid.addLayout(ability_layout, 8, 1)
        property_grid.addWidget(BodyLabel("显示"), 9, 0)
        property_grid.addLayout(display_layout, 9, 1)
        property_grid.addWidget(BodyLabel("整体大小"), 10, 0)
        property_grid.addLayout(size_layout, 10, 1)
        property_grid.addWidget(BodyLabel("楼层"), 11, 0)
        property_grid.addWidget(self.floor_value_label, 11, 1)
        property_grid.addWidget(self.transition_mode_label, 12, 0)
        property_grid.addWidget(self.transition_mode_combo, 12, 1)
        property_grid.addWidget(self.manual_interaction_label, 13, 0)
        property_grid.addWidget(self.manual_interaction_combo, 13, 1)

        keyframe_grid.addWidget(BodyLabel("名称"), 0, 0)
        keyframe_grid.addWidget(self.keyframe_name_edit, 0, 1)
        keyframe_grid.addWidget(BodyLabel("备注"), 1, 0)
        keyframe_grid.addWidget(self.keyframe_note_edit, 1, 1)

        surface_grid.addWidget(BodyLabel("状态"), 0, 0)
        surface_grid.addWidget(self.reinforce_button, 0, 1)
        surface_grid.addWidget(self.surface_opening_label, 1, 0)
        surface_grid.addWidget(self.opening_combo, 1, 1)
        surface_grid.addWidget(self.foot_hole_box, 2, 0)
        surface_grid.addWidget(self.gun_hole_box, 2, 1)

        operator_layout = QVBoxLayout(self.operator_page)
        operator_layout.setContentsMargins(16, 12, 16, 16)
        operator_layout.setSpacing(12)
        operator_layout.addWidget(self.property_title)
        operator_layout.addWidget(self.property_hint)
        operator_layout.addWidget(self.selection_label)
        operator_layout.addLayout(property_grid)
        operator_layout.addWidget(self.manual_interactions_hint)
        operator_layout.addWidget(self.delete_operator_button)
        operator_layout.addStretch(1)

        surface_layout = QVBoxLayout(self.surface_page)
        surface_layout.setContentsMargins(16, 12, 16, 16)
        surface_layout.setSpacing(12)
        surface_layout.addWidget(self.surface_title)
        surface_layout.addWidget(self.surface_hint)
        surface_layout.addWidget(self.surface_selection_label)
        surface_layout.addWidget(self.surface_count_label)
        surface_layout.addLayout(surface_grid)
        surface_layout.addStretch(1)

        keyframe_layout = QVBoxLayout(self.keyframe_page)
        keyframe_layout.setContentsMargins(16, 12, 16, 16)
        keyframe_layout.setSpacing(12)
        keyframe_layout.addWidget(self.keyframe_title)
        keyframe_layout.addWidget(self.keyframe_hint)
        keyframe_layout.addLayout(keyframe_grid)
        keyframe_layout.addStretch(1)

        self.section_tabs.addTab(self.operator_page, "干员")
        self.section_tabs.addTab(self.surface_page, "装修")
        self.section_tabs.addTab(self.keyframe_page, "关键帧")

        layout.addWidget(self.section_tabs, 1)
        self.setTabOrder(self.name_edit, self.side_combo)
        self.setTabOrder(self.side_combo, self.operator_combo)
        self.setTabOrder(self.operator_combo, self.rotation_slider)
        self.setTabOrder(self.rotation_slider, self.show_icon_box)
        self.setTabOrder(self.show_icon_box, self.show_name_box)
        self.setTabOrder(self.show_name_box, self.operator_size_slider)
        self.set_active_section("operator")
        self._apply_theme()

    def refresh_theme(self) -> None:
        self._apply_theme()
        self.manual_interaction_combo.refresh_theme()
        self.delete_operator_button.setStyleSheet(subtle_danger_button_stylesheet())

    def set_active_section(self, section: str) -> None:
        mapping = {
            "operator": 0,
            "surface": 1,
            "keyframe": 2,
        }
        index = mapping.get(section, mapping["operator"])
        self._active_section = section if section in mapping else "operator"
        self.section_tabs.setCurrentIndex(index)

    def active_section(self) -> str:
        return {
            0: "operator",
            1: "surface",
            2: "keyframe",
        }.get(self.section_tabs.currentIndex(), getattr(self, "_active_section", "operator"))

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            f"#{self.objectName()} {{"
            "background: transparent;"
            "border: none;"
            "}"
            + tab_widget_stylesheet()
        )
        self.delete_operator_button.setStyleSheet(subtle_danger_button_stylesheet())


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
        x = map_rect.left() + (map_rect.width() - self.width()) // 2
        y = map_rect.bottom() - self.height() - 12
        self.move(x, y)
        self.raise_()

    def _apply_theme(self) -> None:
        self.setStyleSheet(floating_panel_stylesheet("playback-panel"))

    def refresh_theme(self) -> None:
        self._apply_theme()
