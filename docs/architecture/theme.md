# Theme System

## Goal

The UI theme is centralized in:

- `src/r6_tactics_board/presentation/styles/theme.py`

This file is the single source of truth for:

- page/window background colors
- card and overlay surfaces
- timeline/table colors
- canvas/grid colors
- operator and interaction marker colors
- overview scene colors

## Theme Layers

The project currently uses two theme layers:

1. `qfluentwidgets` global theme
   - switched by `setTheme(Theme.DARK | Theme.LIGHT)`
   - persisted in `config/config.json`

2. local presentation theme tokens
   - implemented in `presentation/styles/theme.py`
   - used by custom widgets that are not fully covered by Fluent defaults

## Core Tokens

### Dark

| Token | Color |
| --- | --- |
| `window_bg` | `#11161D` |
| `page_bg` | `#181D25` |
| `card_bg` | `#202733` |
| `card_bg_alt` | `#242D39` |
| `card_border` | `#394556` |
| `text_primary` | `#F3F4F6` |
| `text_secondary` | `#CBD5E1` |
| `text_muted` | `#94A3B8` |
| `accent` | `#60A5FA` |
| `accent_strong` | `#3B82F6` |
| `accent_warn` | `#FACC15` |
| `canvas_bg` | `#202020` |
| `canvas_grid` | `#2C2C2C` |
| `overview_bg` | `#202020` |

### Light

| Token | Color |
| --- | --- |
| `window_bg` | `#EFF3F8` |
| `page_bg` | `#F8FAFC` |
| `card_bg` | `#FFFFFF` |
| `card_bg_alt` | `#F8FBFF` |
| `card_border` | `#D7E0EA` |
| `text_primary` | `#0F172A` |
| `text_secondary` | `#334155` |
| `text_muted` | `#64748B` |
| `accent` | `#2563EB` |
| `accent_strong` | `#1D4ED8` |
| `accent_warn` | `#D97706` |
| `canvas_bg` | `#F4F7FB` |
| `canvas_grid` | `#D7E0EA` |
| `overview_bg` | `#EEF2F7` |

## Shared Style Helpers

`theme.py` currently exposes these shared helpers:

- `main_window_stylesheet()`
- `page_stylesheet()`
- `card_stylesheet()`
- `floating_panel_stylesheet()`
- `popup_combo_stylesheet()`
- `timeline_table_stylesheet()`

Color helpers are also exposed for:

- canvas
- preview routes
- operator markers
- interaction markers
- overview scene labels/routes

## Refresh Strategy

Theme refresh is handled in two ways:

1. Fluent theme switch:
   - `setTheme(..., save=True)` updates the global Fluent theme

2. Custom widget refresh:
   - pages and shell connect to `qconfig.themeChangedFinished`
   - custom pages call `refresh_theme()`
   - editor/debug pages defer the first refresh with `QTimer.singleShot(0, ...)`
     because immediate refresh during construction can destabilize graphics/GL widgets

## Files That Consume Theme Tokens

- `presentation/shell/main_window.py`
- `presentation/pages/assets/assets_page.py`
- `presentation/pages/debug/debug_page.py`
- `presentation/pages/editor/editor_page.py`
- `presentation/pages/esports/esports_page.py`
- `presentation/pages/settings/settings_page.py`
- `presentation/widgets/editor/editor_panels.py`
- `presentation/widgets/timeline/timeline_widget.py`
- `presentation/widgets/canvas/map_scene.py`
- `presentation/widgets/canvas/map_debug_scene.py`
- `presentation/widgets/canvas/operator_item.py`
- `presentation/widgets/canvas/map_interaction_item.py`
- `presentation/widgets/canvas/overview_scene.py`
- `presentation/widgets/canvas/overview_view.py`

## Rules

- Do not introduce new hard-coded UI colors outside `presentation/styles/theme.py` unless there is a very strong reason.
- Prefer adding a new token/helper over duplicating a literal `#xxxxxx`.
- If a custom widget does its own painting, it must read colors from `theme.py`.
- If a page has a large background surface, it must be covered by `page_stylesheet()` or `card_stylesheet()`.
- All text files remain `UTF-8 + LF`.
