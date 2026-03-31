from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QVector4D
from pyqtgraph.opengl import GLViewWidget

from r6_tactics_board.infrastructure.assets.asset_registry import MapAsset
from r6_tactics_board.presentation.widgets.canvas.overview_scene import OverviewScene


class OverviewView(GLViewWidget):
    viewport_resized = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setBackgroundColor("#202020")
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

    def set_preview_routes(self, routes) -> None:
        self._overview_scene.set_preview_routes(routes)

    def paintGL(self) -> None:  # noqa: N802
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
            if overlay.display_mode == "custom_name":
                self._paint_name_overlay(painter, center, forward, overlay.custom_name, overlay.selected)
            else:
                self._paint_icon_overlay(
                    painter,
                    center,
                    forward,
                    overlay.icon_pixmap,
                    overlay.operator_key,
                    overlay.selected,
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
        selected: bool,
    ) -> None:
        pen = QPen(QColor("#F5F5F5"), 2)
        fill = QColor("#2B88D8")
        if selected:
            pen.setColor(QColor("#FFD54F"))
            pen.setWidth(3)
            fill = QColor("#3598EB")

        direction = forward - center
        length = max((direction.x() ** 2 + direction.y() ** 2) ** 0.5, 1.0)
        ux = direction.x() / length
        uy = direction.y() / length
        px = -uy
        py = ux

        arrow_tip = QPointF(center.x() + ux * 18.0, center.y() + uy * 18.0)
        arrow_left = QPointF(center.x() + px * 4.0 + ux * 8.0, center.y() + py * 4.0 + uy * 8.0)
        arrow_right = QPointF(center.x() - px * 4.0 + ux * 8.0, center.y() - py * 4.0 + uy * 8.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawPolygon(QPolygonF([arrow_tip, arrow_left, arrow_right]))

        icon_rect = QRectF(center.x() - 12.0, center.y() - 12.0, 24.0, 24.0)
        painter.setPen(pen)
        if icon_pixmap.isNull():
            painter.setBrush(fill)
            painter.drawEllipse(icon_rect)
        else:
            painter.setBrush(QColor("#101214"))
            painter.drawEllipse(icon_rect)
            clip_path = QPainterPath()
            clip_path.addEllipse(icon_rect)
            painter.save()
            painter.setClipPath(clip_path)
            painter.drawPixmap(icon_rect.toRect(), icon_pixmap)
            painter.restore()

        painter.setPen(QColor(255, 255, 255, 190))
        painter.setFont(QFont("Microsoft YaHei UI", 6))
        painter.drawText(
            QRectF(center.x() - 10.0, center.y() - 7.0, 20.0, 14.0),
            int(Qt.AlignmentFlag.AlignCenter),
            operator_key[:2].upper() if operator_key else "",
        )

    @staticmethod
    def _paint_name_overlay(
        painter: QPainter,
        center: QPointF,
        forward: QPointF,
        custom_name: str,
        selected: bool,
    ) -> None:
        pen = QPen(QColor("#F5F5F5"), 2)
        fill = QColor("#1F5E8C")
        if selected:
            pen.setColor(QColor("#FFD54F"))
            pen.setWidth(3)
            fill = QColor("#266E9F")

        direction = forward - center
        length = max((direction.x() ** 2 + direction.y() ** 2) ** 0.5, 1.0)
        ux = direction.x() / length
        uy = direction.y() / length
        px = -uy
        py = ux

        arrow_tip = QPointF(center.x() + ux * 26.0, center.y() + uy * 26.0)
        arrow_left = QPointF(center.x() + px * 6.0 + ux * 10.0, center.y() + py * 6.0 + uy * 10.0)
        arrow_right = QPointF(center.x() - px * 6.0 + ux * 10.0, center.y() - py * 6.0 + uy * 10.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawPolygon(QPolygonF([arrow_tip, arrow_left, arrow_right]))

        rect = QRectF(center.x() - 52.0, center.y() - 18.0, 104.0, 36.0)
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 10.0, 10.0)
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), custom_name)
