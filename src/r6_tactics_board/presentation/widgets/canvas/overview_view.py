from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QPainterPath, QPen, QPolygonF, QVector4D
from pyqtgraph.opengl import GLViewWidget

from r6_tactics_board.infrastructure.assets.asset_registry import MapAsset
from r6_tactics_board.presentation.styles.theme import (
    operator_arrow_color,
    operator_icon_background_color,
    operator_icon_fill_color,
    operator_name_fill_color,
    operator_name_text_color,
    operator_pen_color,
    operator_text_color,
    overview_background_color,
)
from r6_tactics_board.presentation.widgets.canvas.overview_scene import OverviewScene


class OverviewView(GLViewWidget):
    viewport_resized = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._pending_theme_refresh = False
        self.setBackgroundColor(overview_background_color())
        self._overview_scene = OverviewScene(self)
        self._last_mouse_pos = None

    def overview_scene(self) -> OverviewScene:
        return self._overview_scene

    def set_map_asset(self, asset: MapAsset | None, *, reset_camera: bool = True) -> bool:
        result = self._overview_scene.set_map_asset(asset)
        if result and reset_camera:
            self._overview_scene.reset_camera()
        return result

    def clear_map(self) -> None:
        self._overview_scene.clear_map()

    def reset_view(self) -> None:
        self._overview_scene.reset_camera()

    def sync_operator_states(self, states, *, selected_operator_id: str = "") -> None:
        self._overview_scene.sync_operator_states(states, selected_operator_id=selected_operator_id)

    def set_operator_scale(self, scale: float) -> None:
        self._overview_scene.set_operator_scale(scale)

    def set_preview_routes(self, routes) -> None:
        self._overview_scene.set_preview_routes(routes)

    def paintGL(self) -> None:  # noqa: N802
        if self._pending_theme_refresh:
            self.setBackgroundColor(overview_background_color())
            self._overview_scene.refresh_theme()
            self._pending_theme_refresh = False
        super().paintGL()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._paint_operator_overlays(painter)
        painter.end()

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        self._last_mouse_pos = ev.position() if hasattr(ev, "position") else ev.localPos()
        if ev.button() == Qt.MouseButton.RightButton:
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        lpos = ev.position() if hasattr(ev, "position") else ev.localPos()
        if self._last_mouse_pos is None:
            self._last_mouse_pos = lpos
        diff = lpos - self._last_mouse_pos
        self._last_mouse_pos = lpos

        buttons = ev.buttons()
        if buttons & Qt.MouseButton.LeftButton and buttons & Qt.MouseButton.RightButton:
            self.pan(diff.x(), diff.y(), 0, relative="view")
            ev.accept()
            return
        if buttons == Qt.MouseButton.LeftButton:
            self.orbit(-diff.x(), diff.y())
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.RightButton:
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            self.reset_view()
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        self.viewport_resized.emit()

    def _paint_operator_overlays(self, painter: QPainter) -> None:
        for overlay in self._overview_scene.overlay_operators():
            center = self._project_world(*overlay.world_position)
            forward = self._project_world(*overlay.world_forward)
            if center is None or forward is None:
                continue
            if overlay.show_icon or overlay.show_name:
                self._paint_icon_overlay(
                    painter,
                    center,
                    forward,
                    overlay.icon_pixmap,
                    overlay.operator_key,
                    overlay.show_icon,
                    overlay.show_name,
                    overlay.selected,
                    overlay.operator_scale,
                )

    def _project_world(self, x: float, y: float, z: float) -> QPointF | None:
        viewport = self.getViewport()
        projection = self.projectionMatrix(viewport, viewport)
        view = self.viewMatrix()
        clip = projection * view * QVector4D(x, y, z, 1.0)
        if abs(clip.w()) < 1e-6:
            return None
        ndc_x = clip.x() / clip.w()
        ndc_y = clip.y() / clip.w()
        if clip.w() <= 0:
            return None
        screen_x = (ndc_x + 1.0) * 0.5 * self.width()
        screen_y = (1.0 - ndc_y) * 0.5 * self.height()
        return QPointF(screen_x, screen_y)

    @staticmethod
    def _paint_icon_overlay(
        painter: QPainter,
        center: QPointF,
        forward: QPointF,
        icon_pixmap,
        operator_key: str,
        show_icon: bool,
        show_name: bool,
        selected: bool,
        operator_scale: float,
    ) -> None:
        scale = operator_scale
        pen = QPen(operator_pen_color(selected), 2)
        fill = operator_icon_fill_color(selected)
        if selected:
            pen.setWidth(3)

        direction = forward - center
        length = max((direction.x() ** 2 + direction.y() ** 2) ** 0.5, 1.0)
        ux = direction.x() / length
        uy = direction.y() / length
        px = -uy
        py = ux

        arrow_tip = QPointF(center.x() + ux * (18.0 * scale), center.y() + uy * (18.0 * scale))
        arrow_left = QPointF(center.x() + px * (4.0 * scale) + ux * (8.0 * scale), center.y() + py * (4.0 * scale) + uy * (8.0 * scale))
        arrow_right = QPointF(center.x() - px * (4.0 * scale) + ux * (8.0 * scale), center.y() - py * (4.0 * scale) + uy * (8.0 * scale))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(operator_arrow_color())
        painter.drawPolygon(QPolygonF([arrow_tip, arrow_left, arrow_right]))

        icon_rect = QRectF(center.x() - (12.0 * scale), center.y() - (12.0 * scale), 24.0 * scale, 24.0 * scale)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(icon_rect)
        if show_icon and icon_pixmap.isNull():
            painter.setBrush(fill)
            painter.drawEllipse(icon_rect)
        elif show_icon:
            painter.setBrush(operator_icon_background_color())
            painter.drawEllipse(icon_rect)
            clip_path = QPainterPath()
            clip_path.addEllipse(icon_rect)
            painter.save()
            painter.setClipPath(clip_path)
            painter.drawPixmap(icon_rect.toRect(), icon_pixmap)
            painter.restore()

        if show_name:
            painter.setPen(operator_text_color())
            painter.setFont(QFont("Microsoft YaHei UI", max(6, round(6 * scale))))
            painter.drawText(
                QRectF(center.x() - (10.0 * scale), center.y() - (7.0 * scale), 20.0 * scale, 14.0 * scale),
                int(Qt.AlignmentFlag.AlignCenter),
                operator_key[:2].upper() if operator_key else "",
            )

    def refresh_theme(self) -> None:
        self._pending_theme_refresh = True
        self.update()
