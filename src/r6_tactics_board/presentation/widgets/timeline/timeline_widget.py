from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QFont
from PyQt6.QtWidgets import QHeaderView, QHBoxLayout, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton

from r6_tactics_board.presentation.styles.theme import (
    card_stylesheet,
    item_view_palette,
    scrollbar_stylesheet,
    timeline_table_stylesheet,
)


class TimelineWidget(QWidget):
    add_keyframe_requested = pyqtSignal()
    insert_keyframe_requested = pyqtSignal()
    duplicate_keyframe_requested = pyqtSignal()
    delete_keyframe_requested = pyqtSignal()
    capture_requested = pyqtSignal()
    capture_column_requested = pyqtSignal()
    clear_cell_requested = pyqtSignal()
    cell_selected = pyqtSignal(int, int)
    keyframe_column_moved = pyqtSignal(int, int)
    operator_row_moved = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("timeline-panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._selected_cell: tuple[int, int] | None = None

        self.title_label = BodyLabel("时间轴 / 轨道表格")
        self.add_button = PushButton()
        self.insert_button = PushButton()
        self.duplicate_button = PushButton()
        self.delete_button = PushButton()
        self.capture_button = PushButton()
        self.capture_column_button = PushButton()
        self.clear_button = PushButton()
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
        toolbar.addWidget(self.title_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.insert_button)
        toolbar.addWidget(self.duplicate_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.capture_button)
        toolbar.addWidget(self.capture_column_button)
        toolbar.addWidget(self.clear_button)

        self.table.setMinimumHeight(180)
        self.table.setFrameShape(QTableWidget.Shape.NoFrame)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.verticalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setHighlightSections(True)
        self.table.verticalHeader().setHighlightSections(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_theme()

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
        self.table.cellClicked.connect(self._on_cell_clicked)
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
        self._selected_cell = (
            (current_row, current_column)
            if 0 <= current_row < len(operator_labels) and 0 <= current_column < len(keyframe_labels)
            else None
        )

        for row in range(len(operator_labels)):
            for column in range(len(keyframe_labels)):
                item = QTableWidgetItem("●" if (row, column) in explicit_cells else "")
                item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                if row == current_row and column == current_column:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, column, item)

        for column, note in enumerate(keyframe_notes):
            header_item = self.table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setToolTip(note or keyframe_labels[column])

        if self._selected_cell is not None:
            self.table.setCurrentCell(*self._selected_cell)
        else:
            self.table.clearSelection()

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
    def _on_cell_clicked(self, row: int, column: int) -> None:
        if self._selected_cell == (row, column):
            self._selected_cell = None
            self.table.clearSelection()
            self.cell_selected.emit(-1, column)
            return

        self._selected_cell = (row, column)
        self.cell_selected.emit(row, column)

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

    def _apply_theme(self) -> None:
        self.setStyleSheet(card_stylesheet(self.objectName()))
        self.table.setStyleSheet(timeline_table_stylesheet())
        palette = item_view_palette()
        self.table.setPalette(palette)
        self.table.viewport().setPalette(palette)
        self.table.horizontalHeader().setPalette(palette)
        self.table.verticalHeader().setPalette(palette)
        self.table.horizontalHeader().viewport().setPalette(palette)
        self.table.verticalHeader().viewport().setPalette(palette)
        self.table.setAutoFillBackground(True)
        self.table.viewport().setAutoFillBackground(True)
        self.table.horizontalHeader().setAutoFillBackground(True)
        self.table.verticalHeader().setAutoFillBackground(True)
        self.table.horizontalHeader().viewport().setAutoFillBackground(True)
        self.table.verticalHeader().viewport().setAutoFillBackground(True)
        self.table.verticalScrollBar().setStyleSheet(scrollbar_stylesheet())
        self.table.horizontalScrollBar().setStyleSheet(scrollbar_stylesheet())
        text_brush = QBrush(palette.text().color())
        base_brush = QBrush(palette.base().color())
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is None:
                    continue
                item.setForeground(text_brush)
                item.setBackground(base_brush)

    def refresh_theme(self) -> None:
        self._apply_theme()
