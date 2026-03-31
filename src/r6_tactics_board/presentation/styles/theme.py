from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QColor
from qfluentwidgets import Theme, isDarkTheme, qconfig
from qfluentwidgets.common.style_sheet import updateStyleSheet

from r6_tactics_board.domain.models import MapInteractionType
from r6_tactics_board.infrastructure.diagnostics.debug_logging import debug_log

_THEME_EVENTS = {
    getattr(QEvent.Type, "PaletteChange"),
    getattr(QEvent.Type, "ApplicationPaletteChange"),
    getattr(QEvent.Type, "StyleChange"),
}

_DARK_TOKENS = {
    "window_bg": "#11161D",
    "page_bg": "#181D25",
    "card_bg": "#202733",
    "card_bg_alt": "#242D39",
    "card_border": "#394556",
    "overlay_bg": "rgba(24, 29, 37, 228)",
    "overlay_border": "rgba(255, 255, 255, 0.10)",
    "popup_bg": "rgba(24, 29, 37, 238)",
    "popup_hover": "rgba(96, 165, 250, 0.95)",
    "popup_selection": "rgba(96, 165, 250, 0.24)",
    "table_bg": "rgba(17, 22, 29, 0.96)",
    "table_header_bg": "rgba(31, 39, 51, 0.98)",
    "table_grid": "rgba(255, 255, 255, 0.08)",
    "table_selected_bg": "#315C84",
    "table_selected_border": "#FACC15",
    "text_primary": "#F3F4F6",
    "text_secondary": "#CBD5E1",
    "text_muted": "#94A3B8",
    "accent": "#60A5FA",
    "accent_strong": "#3B82F6",
    "accent_warn": "#FACC15",
    "canvas_bg": "#202020",
    "canvas_grid": "#2C2C2C",
    "overview_bg": "#202020",
}

_LIGHT_TOKENS = {
    "window_bg": "#EFF3F8",
    "page_bg": "#F8FAFC",
    "card_bg": "#FFFFFF",
    "card_bg_alt": "#F8FBFF",
    "card_border": "#D7E0EA",
    "overlay_bg": "rgba(248, 250, 252, 236)",
    "overlay_border": "rgba(15, 23, 42, 0.12)",
    "popup_bg": "rgba(255, 255, 255, 0.98)",
    "popup_hover": "rgba(37, 99, 235, 0.95)",
    "popup_selection": "rgba(59, 130, 246, 0.14)",
    "table_bg": "rgba(255, 255, 255, 0.98)",
    "table_header_bg": "rgba(241, 245, 249, 0.98)",
    "table_grid": "rgba(148, 163, 184, 0.35)",
    "table_selected_bg": "#DBEAFE",
    "table_selected_border": "#2563EB",
    "text_primary": "#0F172A",
    "text_secondary": "#334155",
    "text_muted": "#64748B",
    "accent": "#2563EB",
    "accent_strong": "#1D4ED8",
    "accent_warn": "#D97706",
    "canvas_bg": "#F4F7FB",
    "canvas_grid": "#D7E0EA",
    "overview_bg": "#EEF2F7",
}


def is_theme_change_event(event: QEvent) -> bool:
    return event.type() in _THEME_EVENTS


def apply_theme(theme: Theme, *, save: bool, lazy: bool = True) -> None:
    current_theme = getattr(qconfig, "theme", None)
    if current_theme == theme:
        debug_log(f"theme: apply skipped same theme={theme}")
        return

    debug_log(f"theme: apply start theme={theme} save={save} lazy={lazy}")
    qconfig.themeMode.value = theme
    qconfig.theme = theme

    if save:
        config_file = Path(qconfig._cfg.file)
        debug_log(f"theme: saving config -> {config_file}")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with config_file.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(qconfig._cfg.toDict(), handle, ensure_ascii=False, indent=4)
        debug_log("theme: config saved")

    debug_log("theme: update stylesheet start")
    updateStyleSheet(lazy)
    debug_log("theme: update stylesheet done")
    qconfig.themeChangedFinished.emit()
    debug_log("theme: themeChangedFinished emitted")


def theme_tokens() -> dict[str, str]:
    return _DARK_TOKENS if isDarkTheme() else _LIGHT_TOKENS


def hex_palette() -> dict[str, str]:
    tokens = theme_tokens()
    return {
        key: value
        for key, value in tokens.items()
        if isinstance(value, str) and value.startswith("#")
    }


def page_stylesheet(object_name: str) -> str:
    tokens = theme_tokens()
    return (
        f"#{object_name} {{"
        f"background-color: {tokens['page_bg']};"
        "}"
    )


def card_stylesheet(object_name: str) -> str:
    tokens = theme_tokens()
    return (
        f"#{object_name} {{"
        f"background-color: {tokens['card_bg']};"
        f"border: 1px solid {tokens['card_border']};"
        "border-radius: 14px;"
        "}"
    )


def main_window_stylesheet(object_name: str, stack_object_name: str) -> str:
    tokens = theme_tokens()
    return (
        f"#{object_name} {{"
        f"background-color: {tokens['window_bg']};"
        "}"
        f"#{stack_object_name} {{"
        "background: transparent;"
        "}"
    )


def floating_panel_stylesheet(object_name: str) -> str:
    tokens = theme_tokens()
    return (
        f"#{object_name} {{"
        f"background-color: {tokens['overlay_bg']};"
        f"border: 1px solid {tokens['overlay_border']};"
        "border-radius: 10px;"
        "}"
    )


def popup_combo_stylesheet() -> str:
    tokens = theme_tokens()
    disabled_fg = "rgba(243, 244, 246, 0.45)" if isDarkTheme() else "rgba(15, 23, 42, 0.40)"
    disabled_bg = "rgba(24, 29, 37, 0.60)" if isDarkTheme() else "rgba(241, 245, 249, 0.95)"
    popup_border = "rgba(255, 255, 255, 0.08)" if isDarkTheme() else "rgba(15, 23, 42, 0.10)"
    selection_fg = "#FFFFFF" if isDarkTheme() else tokens["text_primary"]
    border = tokens["card_border"]

    return f"""
QComboBox {{
    background-color: {tokens['card_bg']};
    color: {tokens['text_primary']};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 32px 6px 10px;
    min-height: 34px;
}}
QComboBox:hover {{
    border: 1px solid {tokens['popup_hover']};
}}
QComboBox:focus {{
    border: 1px solid {tokens['popup_hover']};
}}
QComboBox:disabled {{
    color: {disabled_fg};
    background-color: {disabled_bg};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {tokens['popup_bg']};
    color: {tokens['text_primary']};
    border: 1px solid {popup_border};
    outline: none;
    padding: 4px;
    selection-background-color: {tokens['popup_selection']};
    selection-color: {selection_fg};
}}
"""


def timeline_table_stylesheet() -> str:
    tokens = theme_tokens()
    selection_fg = "#FFFFFF" if isDarkTheme() else tokens["text_primary"]
    return f"""
QTableWidget {{
    background-color: {tokens['table_bg']};
    border: 1px solid {tokens['card_border']};
    border-radius: 10px;
    gridline-color: {tokens['table_grid']};
}}
QHeaderView::section {{
    background-color: {tokens['table_header_bg']};
    color: {tokens['text_primary']};
    border: none;
    border-bottom: 1px solid {tokens['table_grid']};
    border-right: 1px solid {tokens['table_grid']};
    padding: 6px 8px;
}}
QTableCornerButton::section {{
    background-color: {tokens['table_header_bg']};
    border: none;
    border-bottom: 1px solid {tokens['table_grid']};
    border-right: 1px solid {tokens['table_grid']};
}}
QTableWidget::item:selected {{
    background-color: {tokens['table_selected_bg']};
    color: {selection_fg};
    border: 2px solid {tokens['table_selected_border']};
}}
"""


def canvas_background_color() -> QColor:
    return QColor(theme_tokens()["canvas_bg"])


def canvas_grid_color() -> QColor:
    return QColor(theme_tokens()["canvas_grid"])


def preview_path_color() -> QColor:
    return QColor(255, 255, 255, 150) if isDarkTheme() else QColor(37, 99, 235, 135)


def preview_route_color() -> QColor:
    return QColor(250, 204, 21, 180) if isDarkTheme() else QColor(217, 119, 6, 180)


def operator_pen_color(selected: bool) -> QColor:
    if isDarkTheme():
        return QColor("#FFD54F") if selected else QColor("#F5F5F5")
    return QColor("#D97706") if selected else QColor("#1E293B")


def operator_icon_fill_color(selected: bool) -> QColor:
    if isDarkTheme():
        return QColor("#3598EB") if selected else QColor("#2B88D8")
    return QColor("#3B82F6") if selected else QColor("#60A5FA")


def operator_name_fill_color(selected: bool) -> QColor:
    if isDarkTheme():
        return QColor("#266E9F") if selected else QColor("#1F5E8C")
    return QColor("#BFDBFE") if selected else QColor("#DBEAFE")


def operator_arrow_color() -> QColor:
    return QColor("#FFFFFF") if isDarkTheme() else QColor("#0F172A")


def operator_icon_background_color() -> QColor:
    return QColor("#101214") if isDarkTheme() else QColor("#FFFFFF")


def operator_text_color() -> QColor:
    return QColor(255, 255, 255, 190) if isDarkTheme() else QColor(15, 23, 42, 205)


def operator_name_text_color() -> QColor:
    return QColor("#FFFFFF") if isDarkTheme() else QColor("#0F172A")


def interaction_fill_color(kind: MapInteractionType) -> QColor:
    if kind == MapInteractionType.STAIRS:
        return QColor("#3B82F6") if isDarkTheme() else QColor("#2563EB")
    return QColor("#F97316") if isDarkTheme() else QColor("#EA580C")


def interaction_border_color(selected: bool, emphasized: bool) -> QColor:
    if selected or emphasized:
        return QColor("#FACC15") if isDarkTheme() else QColor("#D97706")
    return QColor(255, 255, 255, 140) if isDarkTheme() else QColor(15, 23, 42, 110)


def interaction_emphasis_ring_color() -> QColor:
    return QColor(250, 204, 21, 190) if isDarkTheme() else QColor(217, 119, 6, 190)


def interaction_hover_ring_color() -> QColor:
    return QColor(96, 165, 250, 190) if isDarkTheme() else QColor(37, 99, 235, 190)


def interaction_text_color() -> QColor:
    return QColor("#0B1220") if isDarkTheme() else QColor("#FFFFFF")


def interaction_badge_border_color() -> QColor:
    return QColor("#FFF7CC") if isDarkTheme() else QColor("#FED7AA")


def interaction_badge_background_color() -> QColor:
    return QColor("#111827") if isDarkTheme() else QColor("#FFF7ED")


def interaction_badge_text_color() -> QColor:
    return QColor("#FACC15") if isDarkTheme() else QColor("#C2410C")


def overview_background_color() -> str:
    return theme_tokens()["overview_bg"]


def overview_label_color() -> QColor:
    return QColor("#F3F4F6") if isDarkTheme() else QColor("#0F172A")


def overview_route_rgba(selected: bool) -> tuple[float, float, float, float]:
    if isDarkTheme():
        return (0.98, 0.8, 0.08, 0.95) if selected else (1.0, 1.0, 1.0, 0.7)
    return (0.85, 0.45, 0.08, 0.95) if selected else (0.15, 0.23, 0.35, 0.55)
