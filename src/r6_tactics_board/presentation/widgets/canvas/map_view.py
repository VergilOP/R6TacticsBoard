from PyQt6.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsView

from r6_tactics_board.presentation.styles.theme import graphics_view_stylesheet, scrollbar_stylesheet
from r6_tactics_board.presentation.widgets.canvas.map_scene import MapScene


class MapView(QGraphicsView):
    viewport_resized = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(MapScene())
        self._zoom_factor = 1.15
        self._is_panning = False
        self._last_pan_point = QPoint()
        self._init_view()

    def _init_view(self) -> None:
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setStyleSheet(graphics_view_stylesheet())
        style = scrollbar_stylesheet()
        self.verticalScrollBar().setStyleSheet(style)
        self.horizontalScrollBar().setStyleSheet(style)

    def refresh_theme(self) -> None:
        self.setStyleSheet(graphics_view_stylesheet())
        style = scrollbar_stylesheet()
        self.verticalScrollBar().setStyleSheet(style)
        self.horizontalScrollBar().setStyleSheet(style)
        scene = self.scene()
        if scene is not None and hasattr(scene, "refresh_theme"):
            scene.refresh_theme()

    def scene_center(self) -> QPointF:
        return self.mapToScene(self.viewport().rect().center())

    def fit_scene(self) -> None:
        scene = self.scene()
        if scene is None:
            return

        self.resetTransform()
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def reset_view(self) -> None:
        self.fit_scene()

    def wheelEvent(self, event) -> None:  # noqa: N802
        factor = self._zoom_factor if event.angleDelta().y() > 0 else 1 / self._zoom_factor
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._is_panning:
            delta = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self.unsetCursor()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().keyReleaseEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.viewport_resized.emit()
