from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QHeaderView, QHBoxLayout, QSlider, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton


class TimelineWidget(QWidget):
    add_keyframe_requested = pyqtSignal()
    insert_keyframe_requested = pyqtSignal()
    duplicate_keyframe_requested = pyqtSignal()
    delete_keyframe_requested = pyqtSignal()
    capture_requested = pyqtSignal()
    capture_column_requested = pyqtSignal()
    clear_cell_requested = pyqtSignal()
    previous_column_requested = pyqtSignal()
    next_column_requested = pyqtSignal()
    play_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    duration_changed = pyqtSignal(int)
    cell_selected = pyqtSignal(int, int)
    keyframe_column_moved = pyqtSignal(int, int)
    operator_row_moved = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()

        self.title_label = BodyLabel("时间轴 / 轨道表格")
        self.add_button = PushButton()
        self.insert_button = PushButton()
        self.duplicate_button = PushButton()
        self.delete_button = PushButton()
        self.capture_button = PushButton()
        self.capture_column_button = PushButton()
        self.clear_button = PushButton()
        self.previous_button = PushButton()
        self.next_button = PushButton()
        self.play_button = PushButton()
        self.pause_button = PushButton()
        self.duration_label = BodyLabel("过渡 700 ms")
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.table = QTableWidget()

        self._init_ui()
        self._init_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.add_button.setText("新增关键帧列")
        self.insert_button.setText("在后方插入列")
        self.duplicate_button.setText("复制当前列")
        self.delete_button.setText("删除当前列")
        self.capture_button.setText("记录当前干员")
        self.capture_column_button.setText("记录当前列全部干员")
        self.clear_button.setText("清空当前单元格")
        self.previous_button.setText("上一列")
        self.next_button.setText("下一列")
        self.play_button.setText("播放")
        self.pause_button.setText("暂停")

        self.duration_slider.setRange(200, 2000)
        self.duration_slider.setSingleStep(100)
        self.duration_slider.setPageStep(100)
        self.duration_slider.setValue(700)
        self.duration_slider.setMaximumWidth(180)

        toolbar.addWidget(self.title_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.duration_label)
        toolbar.addWidget(self.duration_slider)
        toolbar.addWidget(self.previous_button)
        toolbar.addWidget(self.next_button)
        toolbar.addWidget(self.play_button)
        toolbar.addWidget(self.pause_button)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.insert_button)
        toolbar.addWidget(self.duplicate_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.capture_button)
        toolbar.addWidget(self.capture_column_button)
        toolbar.addWidget(self.clear_button)

        self.table.setMinimumHeight(180)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.verticalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setHighlightSections(True)
        self.table.verticalHeader().setHighlightSections(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(toolbar)
        layout.addWidget(self.table)

    def _init_signals(self) -> None:
        self.add_button.clicked.connect(self.add_keyframe_requested.emit)
        self.insert_button.clicked.connect(self.insert_keyframe_requested.emit)
        self.duplicate_button.clicked.connect(self.duplicate_keyframe_requested.emit)
        self.delete_button.clicked.connect(self.delete_keyframe_requested.emit)
        self.capture_button.clicked.connect(self.capture_requested.emit)
        self.capture_column_button.clicked.connect(self.capture_column_requested.emit)
        self.clear_button.clicked.connect(self.clear_cell_requested.emit)
        self.previous_button.clicked.connect(self.previous_column_requested.emit)
        self.next_button.clicked.connect(self.next_column_requested.emit)
        self.play_button.clicked.connect(self.play_requested.emit)
        self.pause_button.clicked.connect(self.pause_requested.emit)
        self.duration_slider.valueChanged.connect(self._on_duration_changed)
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        self.table.horizontalHeader().sectionMoved.connect(self._on_column_section_moved)
        self.table.verticalHeader().sectionMoved.connect(self._on_row_section_moved)

    def set_grid(
        self,
        operator_labels: list[str],
        keyframe_labels: list[str],
        keyframe_notes: list[str],
        explicit_cells: set[tuple[int, int]],
        current_row: int = -1,
        current_column: int = -1,
        is_playing: bool = False,
    ) -> None:
        self.table.blockSignals(True)
        self.table.horizontalHeader().blockSignals(True)
        self.table.verticalHeader().blockSignals(True)
        self.table.clear()
        self.table.setRowCount(len(operator_labels))
        self.table.setColumnCount(len(keyframe_labels))
        self.table.setVerticalHeaderLabels(operator_labels)
        self.table.setHorizontalHeaderLabels(keyframe_labels)
        self._reset_header_order(self.table.horizontalHeader())
        self._reset_header_order(self.table.verticalHeader())

        for row in range(len(operator_labels)):
            for column in range(len(keyframe_labels)):
                item = QTableWidgetItem("●" if (row, column) in explicit_cells else "")
                item.setTextAlignment(0x84)
                if column == current_column:
                    item.setBackground(QBrush(QColor("#243447")))
                if row == current_row and column == current_column:
                    item.setBackground(QBrush(QColor("#2D4F6C")))
                self.table.setItem(row, column, item)

        for column, note in enumerate(keyframe_notes):
            header_item = self.table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setToolTip(note or keyframe_labels[column])

        if 0 <= current_row < len(operator_labels) and 0 <= current_column < len(keyframe_labels):
            self.table.setCurrentCell(current_row, current_column)
        elif len(operator_labels) > 0 and len(keyframe_labels) > 0 and current_column >= 0:
            self.table.setCurrentCell(0, min(current_column, len(keyframe_labels) - 1))

        self.table.blockSignals(False)
        self.table.horizontalHeader().blockSignals(False)
        self.table.verticalHeader().blockSignals(False)

        has_columns = len(keyframe_labels) > 0
        self.delete_button.setEnabled(has_columns and current_column >= 0)
        self.insert_button.setEnabled(has_columns and current_column >= 0)
        self.duplicate_button.setEnabled(has_columns and current_column >= 0)
        self.capture_button.setEnabled(has_columns and current_column >= 0 and current_row >= 0)
        self.capture_column_button.setEnabled(has_columns)
        self.clear_button.setEnabled(
            (current_row, current_column) in explicit_cells
            if current_row >= 0 and current_column >= 0
            else False
        )
        self.previous_button.setEnabled(has_columns and current_column > 0)
        self.next_button.setEnabled(has_columns and 0 <= current_column < len(keyframe_labels) - 1)
        self.play_button.setEnabled(has_columns and not is_playing and len(keyframe_labels) > 1)
        self.pause_button.setEnabled(is_playing)

    def _on_current_cell_changed(self, current_row: int, current_column: int, *_args) -> None:
        if current_row >= 0 and current_column >= 0:
            self.cell_selected.emit(current_row, current_column)

    def _on_duration_changed(self, value: int) -> None:
        self.duration_label.setText(f"过渡 {value} ms")
        self.duration_changed.emit(value)

    def _on_column_section_moved(self, logical_index: int, old_visual_index: int, new_visual_index: int) -> None:
        if old_visual_index != new_visual_index:
            self.keyframe_column_moved.emit(old_visual_index, new_visual_index)

    def _on_row_section_moved(self, logical_index: int, old_visual_index: int, new_visual_index: int) -> None:
        if old_visual_index != new_visual_index:
            self.operator_row_moved.emit(old_visual_index, new_visual_index)

    @staticmethod
    def _reset_header_order(header: QHeaderView) -> None:
        for logical_index in range(header.count()):
            current_visual_index = header.visualIndex(logical_index)
            if current_visual_index != logical_index:
                header.moveSection(current_visual_index, logical_index)
