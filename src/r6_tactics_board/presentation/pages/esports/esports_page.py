from __future__ import annotations

import json
from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, ComboBox, PushButton, StrongBodyLabel, SubtitleLabel

from r6_tactics_board.domain.esports_models import EsportsMapDataset, EsportsMatchRecord
from r6_tactics_board.infrastructure.assets.asset_registry import AssetRegistry, OperatorCatalogEntry
from r6_tactics_board.infrastructure.esports.esports_store import EsportsStore


class SummaryStatCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()

        self.title_label = BodyLabel(title)
        self.value_label = StrongBodyLabel("-")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class OperatorIconStrip(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()

        self.title_label = StrongBodyLabel(title)
        self.empty_label = BodyLabel("暂无数据")
        self.items_container = QWidget()
        self.items_layout = QHBoxLayout(self.items_container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.items_container)

        self.empty_label.setWordWrap(True)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)

        self.set_names([], None)

    def set_names(
        self,
        names: list[str],
        resolver: Callable[[str], OperatorCatalogEntry | None] | None,
        empty_text: str = "暂无数据",
        hide_when_empty: bool = False,
    ) -> None:
        self.empty_label.setText(empty_text)
        self._clear_items()

        if not names:
            self.empty_label.setVisible(not hide_when_empty)
            self.items_container.hide()
            self.setVisible(not hide_when_empty)
            return

        self.setVisible(True)
        self.empty_label.hide()
        self.items_container.show()

        for name in names:
            entry = resolver(name) if resolver is not None else None
            self.items_layout.addWidget(self._build_item(name, entry))
        self.items_layout.addStretch(1)

    def _clear_items(self) -> None:
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _build_item(name: str, entry: OperatorCatalogEntry | None) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)

        icon_label = QLabel()
        icon_label.setFixedSize(44, 44)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if entry is not None and entry.icon_path:
            pixmap = QPixmap(entry.icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(
                        40,
                        40,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                icon_label.setText("?")
        else:
            icon_label.setText("?")

        name_label = BodyLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        frame.setToolTip(entry.key if entry is not None else f"{name} · 未找到图标")
        return frame


class EsportsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.store = EsportsStore()
        self.asset_registry = AssetRegistry()
        self._current_dataset: EsportsMapDataset | None = None
        self._map_names = {asset.key: asset.name for asset in self.asset_registry.list_map_assets()}

        self.map_combo = ComboBox()
        self.refresh_button = PushButton("刷新电竞数据")
        self.status_label = BodyLabel("请选择地图")

        self.matches_stat_card = SummaryStatCard("总比赛数")
        self.flawless_stat_card = SummaryStatCard("完美回合")
        self.updated_stat_card = SummaryStatCard("最近更新")

        self.summary_blurb_label = BodyLabel("-")
        self.matches_list = QListWidget()

        self.content_tabs = QTabWidget()
        self.winner_label = SubtitleLabel("请选择比赛")
        self.score_label = StrongBodyLabel("-")
        self.event_label = BodyLabel("-")
        self.side_summary_label = BodyLabel("-")
        self.meta_label = BodyLabel("-")
        self.attack_bans_strip = OperatorIconStrip("进攻方禁用")
        self.defense_bans_strip = OperatorIconStrip("防守方禁用")
        self.attack_ops_strip = OperatorIconStrip("进攻方阵容")
        self.defense_ops_strip = OperatorIconStrip("防守方阵容")

        self.source_label = BodyLabel("-")
        self.summary_fields_label = BodyLabel("-")
        self.match_fields_label = BodyLabel("-")
        self.raw_map_block_view = QPlainTextEdit()
        self.match_json_view = QPlainTextEdit()
        self.summary_json_view = QPlainTextEdit()

        self._init_ui()
        self._init_signals()
        self._reload_maps()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(12)
        toolbar_layout.addWidget(BodyLabel("地图"))
        toolbar_layout.addWidget(self.map_combo, 1)
        toolbar_layout.addWidget(self.refresh_button)

        layout.addWidget(SubtitleLabel("电竞历史"))
        layout.addWidget(BodyLabel("优先展示观赛关键信息，包括胜负、比分、赛事信息和 ban 人记录。"))
        layout.addLayout(toolbar_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        stats_layout.addWidget(self.matches_stat_card)
        stats_layout.addWidget(self.flawless_stat_card)
        stats_layout.addWidget(self.updated_stat_card)

        self.summary_blurb_label.setWordWrap(True)
        self.status_label.setWordWrap(True)

        left_layout.addWidget(self.status_label)
        left_layout.addLayout(stats_layout)
        left_layout.addWidget(self.summary_blurb_label)
        left_layout.addWidget(StrongBodyLabel("比赛列表"))
        left_layout.addWidget(self.matches_list, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        right_layout.addWidget(self.content_tabs, 1)

        self._init_match_tab()
        self._init_data_tab()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

    def _init_match_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero_frame = QFrame()
        hero_frame.setFrameShape(QFrame.Shape.StyledPanel)
        hero_layout = QVBoxLayout(hero_frame)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(8)

        for label in (
            self.winner_label,
            self.event_label,
            self.side_summary_label,
            self.meta_label,
        ):
            label.setWordWrap(True)
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        hero_layout.addWidget(self.winner_label)
        hero_layout.addWidget(self.score_label)
        hero_layout.addWidget(self.event_label)
        hero_layout.addWidget(self.side_summary_label)
        hero_layout.addWidget(self.meta_label)

        layout.addWidget(hero_frame)
        layout.addWidget(self.attack_bans_strip)
        layout.addWidget(self.defense_bans_strip)
        layout.addWidget(self.attack_ops_strip)
        layout.addWidget(self.defense_ops_strip)
        layout.addStretch(1)

        self.content_tabs.addTab(tab, "比赛视图")

    def _init_data_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for label in (self.source_label, self.summary_fields_label, self.match_fields_label):
            label.setWordWrap(True)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.addWidget(BodyLabel("数据来源"), 0, 0)
        grid.addWidget(self.source_label, 0, 1)
        grid.addWidget(BodyLabel("summary.json 字段"), 1, 0)
        grid.addWidget(self.summary_fields_label, 1, 1)
        grid.addWidget(BodyLabel("raw_matches.json 字段"), 2, 0)
        grid.addWidget(self.match_fields_label, 2, 1)

        for editor in (self.raw_map_block_view, self.match_json_view, self.summary_json_view):
            editor.setReadOnly(True)
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        raw_tabs = QTabWidget()
        raw_tabs.addTab(self.match_json_view, "比赛 JSON")
        raw_tabs.addTab(self.summary_json_view, "汇总 JSON")
        raw_tabs.addTab(self.raw_map_block_view, "原始地图块")

        layout.addLayout(grid)
        layout.addWidget(raw_tabs, 1)

        self.content_tabs.addTab(tab, "数据视图")

    def _init_signals(self) -> None:
        self.refresh_button.clicked.connect(self._reload_maps)
        self.map_combo.currentIndexChanged.connect(self._load_selected_map)
        self.matches_list.currentRowChanged.connect(self._show_match_at_row)

    def _reload_maps(self) -> None:
        previous_key = str(self.map_combo.currentData() or "")
        entries = self.store.list_map_entries()

        self.map_combo.blockSignals(True)
        self.map_combo.clear()

        for index, entry in enumerate(entries):
            display_name = self._map_names.get(entry.map_key, entry.display_name)
            self.map_combo.addItem(f"{display_name} ({entry.total_matches} 场)")
            self.map_combo.setItemData(index, entry.map_key)

        self.map_combo.blockSignals(False)

        if not entries:
            self._current_dataset = None
            self.status_label.setText("未找到电竞数据目录或地图数据为空")
            self._clear_summary()
            self._clear_match_list()
            self._clear_details()
            return

        target_index = 0
        for index in range(self.map_combo.count()):
            if self.map_combo.itemData(index) == previous_key:
                target_index = index
                break
        self.map_combo.setCurrentIndex(target_index)
        self._load_selected_map()

    def _load_selected_map(self) -> None:
        map_key = self.map_combo.currentData()
        if not map_key:
            return

        dataset = self.store.load_map_dataset(str(map_key))
        self._current_dataset = dataset

        if dataset is None:
            self.status_label.setText("地图数据读取失败")
            self._clear_summary()
            self._clear_match_list()
            self._clear_details()
            return

        self._refresh_summary(dataset)
        self._fill_match_list(dataset)
        if dataset.matches:
            self.matches_list.setCurrentRow(0)
        else:
            self._clear_details()

    def _refresh_summary(self, dataset: EsportsMapDataset) -> None:
        summary = dataset.summary
        display_name = self._map_names.get(dataset.map_key, dataset.map_key)

        self.status_label.setText(f"当前地图：{display_name}")
        self.matches_stat_card.set_value(
            str(summary.total_matches if summary is not None else len(dataset.matches))
        )
        self.flawless_stat_card.set_value(str(summary.flawless_count if summary is not None else 0))
        self.updated_stat_card.set_value(summary.last_updated if summary is not None else "-")
        self.source_label.setText(dataset.source)
        self.summary_fields_label.setText(", ".join(dataset.summary_fields) if dataset.summary_fields else "-")
        self.match_fields_label.setText(", ".join(dataset.match_fields) if dataset.match_fields else "-")

        if summary is None:
            self.summary_blurb_label.setText("当前地图没有 summary.json，正在直接使用比赛记录。")
            self.summary_json_view.setPlainText("{}")
            return

        ranked = sorted(summary.teams.items(), key=lambda item: (-item[1], item[0]))
        teams_text = " / ".join(f"{team} ({count})" for team, count in ranked[:6]) if ranked else "暂无队伍统计"
        self.summary_blurb_label.setText(
            f"{summary.map_name} 共收录 {summary.total_matches} 场比赛。高频队伍：{teams_text}"
        )
        self.summary_json_view.setPlainText(json.dumps(summary.raw_data, ensure_ascii=False, indent=2))

    def _fill_match_list(self, dataset: EsportsMapDataset) -> None:
        self.matches_list.clear()

        if not dataset.matches:
            placeholder = QListWidgetItem("(暂无比赛记录)")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.matches_list.addItem(placeholder)
            return

        for index, match in enumerate(dataset.matches):
            item = QListWidgetItem(self._format_match_item(match))
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setToolTip(self._format_match_tooltip(match))
            self.matches_list.addItem(item)

    def _show_match_at_row(self, row: int) -> None:
        dataset = self._current_dataset
        if dataset is None or row < 0 or row >= len(dataset.matches):
            self._clear_details()
            return

        match = dataset.matches[row]
        winner = match.winner_team or "未分胜负"
        loser = match.loser_team

        self.winner_label.setText(
            f"胜者：{winner}" if winner != "未分胜负" else "结果：未分胜负"
        )
        self.score_label.setText(
            f"{match.atk_team or '-'} {match.scoreline} {match.def_team or '-'}"
        )
        self.event_label.setText(
            " / ".join(part for part in [match.date, match.tournament, match.stage] if part) or "-"
        )
        side_lines = [
            f"进攻方：{match.atk_team or '-'}",
            f"防守方：{match.def_team or '-'}",
        ]
        if loser:
            side_lines.append(f"败者：{loser}")
        self.side_summary_label.setText(" / ".join(side_lines))

        meta_parts = [
            f"先攻：{match.first_attack}" if match.first_attack else "",
            f"选图：{match.pick}" if match.pick else "",
            f"总击杀：{match.total_deaths}",
            f"比赛 ID：{match.match_id}" if match.match_id else "",
            f"来源：{match.match_ref}" if match.match_ref else "",
        ]
        self.meta_label.setText(" / ".join(part for part in meta_parts if part) or "-")

        self.attack_bans_strip.set_names(match.atk_bans, self._resolve_operator_icon, "暂无禁用记录")
        self.defense_bans_strip.set_names(match.def_bans, self._resolve_operator_icon, "暂无禁用记录")
        self.attack_ops_strip.set_names(
            match.atk_operators,
            self._resolve_operator_icon,
            hide_when_empty=True,
        )
        self.defense_ops_strip.set_names(
            match.def_operators,
            self._resolve_operator_icon,
            hide_when_empty=True,
        )

        self.match_json_view.setPlainText(json.dumps(match.raw_data, ensure_ascii=False, indent=2))
        self.raw_map_block_view.setPlainText(match.raw_map_block or "(当前记录没有 raw_map_block)")

    def _clear_summary(self) -> None:
        self.matches_stat_card.set_value("-")
        self.flawless_stat_card.set_value("-")
        self.updated_stat_card.set_value("-")
        self.summary_blurb_label.setText("-")
        self.source_label.setText("-")
        self.summary_fields_label.setText("-")
        self.match_fields_label.setText("-")
        self.summary_json_view.setPlainText("{}")

    def _clear_match_list(self) -> None:
        self.matches_list.clear()

    def _clear_details(self) -> None:
        self.winner_label.setText("请选择比赛")
        self.score_label.setText("-")
        self.event_label.setText("-")
        self.side_summary_label.setText("-")
        self.meta_label.setText("-")
        self.attack_bans_strip.set_names([], self._resolve_operator_icon, "暂无禁用记录")
        self.defense_bans_strip.set_names([], self._resolve_operator_icon, "暂无禁用记录")
        self.attack_ops_strip.set_names([], self._resolve_operator_icon, hide_when_empty=True)
        self.defense_ops_strip.set_names([], self._resolve_operator_icon, hide_when_empty=True)
        self.match_json_view.setPlainText("{}")
        self.raw_map_block_view.setPlainText("")

    def _resolve_operator_icon(self, name: str) -> OperatorCatalogEntry | None:
        return self.asset_registry.find_operator_catalog_entry(name)

    @staticmethod
    def _format_match_item(match: EsportsMatchRecord) -> str:
        winner = match.winner_team or "平局"
        lead = match.date or match.tournament or "日期未知"
        return " | ".join(
            part
            for part in [
                lead,
                f"{winner} {match.scoreline}",
                f"{match.atk_team or '-'} vs {match.def_team or '-'}",
            ]
            if part
        )

    @staticmethod
    def _format_match_tooltip(match: EsportsMatchRecord) -> str:
        return " / ".join(
            part
            for part in [
                match.tournament,
                match.stage,
                f"{match.atk_team} vs {match.def_team}".strip(),
            ]
            if part
        )
