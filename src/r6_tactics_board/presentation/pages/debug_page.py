from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton, SubtitleLabel


class DebugPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(SubtitleLabel("测试调试页面"))
        layout.addWidget(
            BodyLabel(
                "这个页面用于后续放置开发期工具，例如场景状态检查、"
                "坐标调试、关键帧预览、日志输出和临时功能开关。"
            )
        )
        layout.addWidget(PushButton("预留按钮"))
        layout.addStretch(1)
