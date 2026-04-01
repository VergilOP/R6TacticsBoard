from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, ComboBox, PrimaryPushButton, PushButton, SubtitleLabel, Theme, isDarkTheme

from r6_tactics_board.presentation.styles.theme import (
    apply_theme,
    card_stylesheet,
    item_view_palette,
    list_widget_stylesheet,
    page_stylesheet,
    plain_text_stylesheet,
    popup_combo_stylesheet,
    scrollbar_stylesheet,
    splitter_stylesheet,
    timeline_table_stylesheet,
)


class ThemeAuditPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("theme-audit-page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("themePage", True)

        self._widget_targets: dict[str, Callable[[], QWidget | None]] = {}
        self._probe_targets: dict[str, Callable[[], str]] = {}

        self.dark_button = PushButton("切到深色")
        self.light_button = PushButton("切到浅色")
        self.refresh_button = PrimaryPushButton("刷新排查报告")

        self.sample_combo = ComboBox()
        self.sample_list = QListWidget()
        self.sample_text = QPlainTextEdit()
        self.sample_table = QTableWidget(8, 4)
        self.sample_tabs = QSplitter(Qt.Orientation.Vertical)
        self.top_tab_text = QPlainTextEdit()
        self.bottom_tab_text = QPlainTextEdit()
        self.report_view = QPlainTextEdit()

        self._init_ui()
        self._init_signals()
        self._seed_samples()
        self.refresh_theme()
        self.refresh_report()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        toolbar.addWidget(self.dark_button)
        toolbar.addWidget(self.light_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addStretch(1)

        self.report_view.setReadOnly(True)
        self.sample_text.setReadOnly(True)
        self.top_tab_text.setReadOnly(True)
        self.bottom_tab_text.setReadOnly(True)
        self.sample_tabs.setChildrenCollapsible(False)
        self.sample_list.setMinimumHeight(160)
        self.sample_text.setMinimumHeight(160)
        self.sample_table.setMinimumHeight(220)
        self.report_view.setMinimumWidth(520)

        sample_panel = QWidget()
        sample_panel.setObjectName("theme-audit-sample-card")
        sample_layout = QGridLayout(sample_panel)
        sample_layout.setContentsMargins(16, 16, 16, 16)
        sample_layout.setHorizontalSpacing(12)
        sample_layout.setVerticalSpacing(12)

        sample_layout.addWidget(BodyLabel("ComboBox"), 0, 0)
        sample_layout.addWidget(self.sample_combo, 0, 1)
        sample_layout.addWidget(BodyLabel("List"), 1, 0)
        sample_layout.addWidget(self.sample_list, 1, 1)
        sample_layout.addWidget(BodyLabel("PlainText"), 2, 0)
        sample_layout.addWidget(self.sample_text, 2, 1)
        sample_layout.addWidget(BodyLabel("Table"), 3, 0)
        sample_layout.addWidget(self.sample_table, 3, 1)
        sample_layout.addWidget(BodyLabel("Splitter"), 4, 0)
        sample_layout.addWidget(self.sample_tabs, 4, 1)

        self.sample_tabs.addWidget(self.top_tab_text)
        self.sample_tabs.addWidget(self.bottom_tab_text)
        self.sample_tabs.setStretchFactor(0, 1)
        self.sample_tabs.setStretchFactor(1, 1)

        container = QSplitter(Qt.Orientation.Horizontal)
        container.setChildrenCollapsible(False)
        container.addWidget(sample_panel)
        container.addWidget(self.report_view)
        container.setStretchFactor(0, 0)
        container.setStretchFactor(1, 1)
        self.container_splitter = container

        layout.addWidget(SubtitleLabel("主题排查"))
        layout.addWidget(
            BodyLabel(
                "这里同时展示主题示例控件和实际页面控件的调试信息，用于排查深浅色切换后仍残留旧颜色的问题。"
            )
        )
        layout.addLayout(toolbar)
        layout.addWidget(container, 1)

    def _init_signals(self) -> None:
        self.dark_button.clicked.connect(lambda: self._switch_theme(Theme.DARK))
        self.light_button.clicked.connect(lambda: self._switch_theme(Theme.LIGHT))
        self.refresh_button.clicked.connect(self.refresh_report)

    def _seed_samples(self) -> None:
        self.sample_combo.addItem("样例地图 A")
        self.sample_combo.addItem("样例地图 B")

        for index in range(24):
            self.sample_list.addItem(f"列表项 {index + 1}")

        self.sample_text.setPlainText(
            "这是主题排查用的只读文本区域。\n"
            "它需要在浅色模式下保持浅背景 + 深文字，在深色模式下反过来。\n\n"
            + "\n".join(f"Line {index + 1}: sample text" for index in range(20))
        )

        self.sample_table.setHorizontalHeaderLabels(["A", "B", "C", "D"])
        for row in range(self.sample_table.rowCount()):
            for column in range(self.sample_table.columnCount()):
                self.sample_table.setItem(row, column, QTableWidgetItem(f"{row},{column}"))
        self.sample_table.setCurrentCell(1, 1)

        self.top_tab_text.setPlainText("上半区 splitter / plain text 样例")
        self.bottom_tab_text.setPlainText("下半区 splitter / plain text 样例")

    def set_widget_targets(self, targets: dict[str, Callable[[], QWidget | None]]) -> None:
        self._widget_targets = dict(targets)
        self.refresh_report()

    def set_probe_targets(self, probes: dict[str, Callable[[], str]]) -> None:
        self._probe_targets = dict(probes)
        self.refresh_report()

    def _switch_theme(self, theme: Theme) -> None:
        apply_theme(theme, save=False, lazy=False)

    def refresh_theme(self) -> None:
        self.setStyleSheet(
            page_stylesheet(self.objectName()) + card_stylesheet("theme-audit-sample-card")
        )
        list_style = list_widget_stylesheet()
        plain_style = plain_text_stylesheet()
        self.sample_combo.setStyleSheet(popup_combo_stylesheet())
        self.sample_list.setStyleSheet(list_style)
        self.sample_text.setStyleSheet(plain_style)
        self.top_tab_text.setStyleSheet(plain_style)
        self.bottom_tab_text.setStyleSheet(plain_style)
        self.sample_table.setStyleSheet(timeline_table_stylesheet())
        self.sample_tabs.setStyleSheet(splitter_stylesheet())
        self.container_splitter.setStyleSheet(splitter_stylesheet())
        self.report_view.setStyleSheet(plain_style)
        palette = item_view_palette()
        for widget in (self.sample_list, self.sample_text, self.top_tab_text, self.bottom_tab_text, self.report_view):
            widget.setPalette(palette)
            widget.viewport().setPalette(palette)
            widget.verticalScrollBar().setStyleSheet(scrollbar_stylesheet())
            widget.horizontalScrollBar().setStyleSheet(scrollbar_stylesheet())
        self.sample_table.setPalette(palette)
        self.sample_table.viewport().setPalette(palette)
        self.sample_table.horizontalHeader().setPalette(palette)
        self.sample_table.verticalHeader().setPalette(palette)
        self.sample_table.verticalScrollBar().setStyleSheet(scrollbar_stylesheet())
        self.sample_table.horizontalScrollBar().setStyleSheet(scrollbar_stylesheet())
        for row in range(self.sample_table.rowCount()):
            for column in range(self.sample_table.columnCount()):
                item = self.sample_table.item(row, column)
                if item is None:
                    continue
                item.setForeground(palette.text().color())
                item.setBackground(palette.base().color())

    def refresh_report(self) -> None:
        lines = [
            f"当前主题: {'深色' if isDarkTheme() else '浅色'}",
            "",
            "== 样例控件 ==",
        ]
        sample_widgets = {
            "sample_combo": self.sample_combo,
            "sample_list": self.sample_list,
            "sample_text": self.sample_text,
            "sample_table": self.sample_table,
        }
        for label, widget in sample_widgets.items():
            lines.extend(self._describe_widget(label, widget))
            lines.append("")

        if self._widget_targets:
            lines.append("== 实际页面控件 ==")
            for label, getter in self._widget_targets.items():
                widget = getter()
                lines.extend(self._describe_widget(label, widget))
                lines.append("")

        if self._probe_targets:
            lines.append("== 额外探针 ==")
            for label, getter in self._probe_targets.items():
                try:
                    value = getter()
                except Exception as exc:  # pragma: no cover - debug surface
                    value = f"ERROR: {exc}"
                lines.append(f"{label}: {value}")

        self.report_view.setPlainText("\n".join(lines))

    @staticmethod
    def _describe_widget(label: str, widget: QWidget | None) -> list[str]:
        if widget is None:
            return [f"{label}: MISSING"]

        palette = widget.palette()
        viewport = widget.viewport() if hasattr(widget, "viewport") else None
        viewport_palette = viewport.palette() if viewport is not None else None
        vscroll = widget.verticalScrollBar() if hasattr(widget, "verticalScrollBar") else None
        hscroll = widget.horizontalScrollBar() if hasattr(widget, "horizontalScrollBar") else None

        lines = [
            f"{label}: {widget.__class__.__name__} objectName={widget.objectName() or '-'}",
            f"  styleSheet_len={len(widget.styleSheet())}",
            (
                "  palette"
                f" window={palette.window().color().name()}"
                f" base={palette.base().color().name()}"
                f" text={palette.text().color().name()}"
                f" button={palette.button().color().name()}"
            ),
        ]
        if viewport_palette is not None:
            lines.append(
                "  viewport"
                f" window={viewport_palette.window().color().name()}"
                f" base={viewport_palette.base().color().name()}"
                f" text={viewport_palette.text().color().name()}"
            )
        if isinstance(widget, QTableWidget):
            current_item = widget.currentItem()
            if current_item is not None:
                lines.append(
                    "  current_item"
                    f" fg={current_item.foreground().color().name()}"
                    f" bg={current_item.background().color().name()}"
                    f" selected={current_item.isSelected()}"
                )
        if vscroll is not None:
            lines.append(
                "  vscroll"
                f" styleSheet_len={len(vscroll.styleSheet())}"
                f" visible={vscroll.isVisible()}"
                f" button={vscroll.palette().button().color().name()}"
                f" base={vscroll.palette().base().color().name()}"
            )
        if hscroll is not None:
            lines.append(
                "  hscroll"
                f" styleSheet_len={len(hscroll.styleSheet())}"
                f" visible={hscroll.isVisible()}"
                f" button={hscroll.palette().button().color().name()}"
                f" base={hscroll.palette().base().color().name()}"
            )
        return lines
