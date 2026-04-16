from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap

_COMPACT_PIXMAP_CACHE: dict[tuple[str, int, int], QPixmap] = {}
_COMPACT_ICON_CACHE: dict[tuple[str, int, int], QIcon] = {}


def compact_asset_pixmap(icon_path: str, target_size: QSize) -> QPixmap:
    """Trim transparent padding so asset icons read larger without resizing widgets."""
    cache_key = (icon_path, target_size.width(), target_size.height())
    if cache_key in _COMPACT_PIXMAP_CACHE:
        return _COMPACT_PIXMAP_CACHE[cache_key]

    source = QPixmap(icon_path) if icon_path else QPixmap()
    if source.isNull():
        return QPixmap()

    if source.width() * source.height() > 512 * 512:
        canvas = QPixmap(target_size)
        canvas.fill(Qt.GlobalColor.transparent)
        scaled = source.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(canvas)
        painter.drawPixmap(
            (target_size.width() - scaled.width()) // 2,
            (target_size.height() - scaled.height()) // 2,
            scaled,
        )
        painter.end()
        _COMPACT_PIXMAP_CACHE[cache_key] = canvas
        return canvas

    image = source.toImage()
    min_x = image.width()
    min_y = image.height()
    max_x = -1
    max_y = -1

    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 8:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if max_x >= min_x and max_y >= min_y:
        source = source.copy(QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1))

    canvas = QPixmap(target_size)
    canvas.fill(Qt.GlobalColor.transparent)
    scaled = source.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(canvas)
    painter.drawPixmap((target_size.width() - scaled.width()) // 2, (target_size.height() - scaled.height()) // 2, scaled)
    painter.end()
    _COMPACT_PIXMAP_CACHE[cache_key] = canvas
    return canvas


def compact_asset_icon(icon_path: str, target_size: QSize) -> QIcon:
    cache_key = (icon_path, target_size.width(), target_size.height())
    if cache_key in _COMPACT_ICON_CACHE:
        return _COMPACT_ICON_CACHE[cache_key]

    pixmap = compact_asset_pixmap(icon_path, target_size)
    icon = QIcon(pixmap) if not pixmap.isNull() else QIcon()
    _COMPACT_ICON_CACHE[cache_key] = icon
    return icon
