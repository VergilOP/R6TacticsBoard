from PyQt6.QtGui import QCloseEvent
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition

from r6_tactics_board.presentation.pages.assets.assets_page import AssetsPage
from r6_tactics_board.presentation.pages.debug.debug_page import DebugPage
from r6_tactics_board.presentation.pages.editor.editor_page import EditorPage
from r6_tactics_board.presentation.pages.esports.esports_page import EsportsPage
from r6_tactics_board.presentation.pages.settings.settings_page import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self) -> None:
        super().__init__()

        self.editor_page = EditorPage()
        self.assets_page = AssetsPage()
        self.esports_page = EsportsPage()
        self.debug_page = DebugPage()
        self.settings_page = SettingsPage()

        self.editor_page.setObjectName("editor-page")
        self.assets_page.setObjectName("assets-page")
        self.esports_page.setObjectName("esports-page")
        self.debug_page.setObjectName("debug-page")
        self.settings_page.setObjectName("settings-page")

        self.assets_page.map_requested.connect(self._open_map_in_editor)
        self.assets_page.operator_requested.connect(self._add_operator_from_assets)

        self.addSubInterface(self.editor_page, FluentIcon.EDIT, "战术编辑")
        self.addSubInterface(self.assets_page, FluentIcon.FOLDER, "资源管理")
        self.addSubInterface(self.esports_page, FluentIcon.HISTORY, "电竞历史")
        self.addSubInterface(self.debug_page, FluentIcon.DEVELOPER_TOOLS, "测试调试")
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM,
        )
        self.navigationInterface.setReturnButtonVisible(False)

        self.setWindowTitle("R6 Tactics Board")
        self.setMinimumSize(1280, 720)
        self.resize(1440, 900)

    def _open_map_in_editor(self, file_path: str) -> None:
        if not self.editor_page.confirm_discard_changes("加载地图"):
            return
        self.editor_page.load_map_from_path(file_path)
        self.switchTo(self.editor_page)

    def _add_operator_from_assets(self, side: str, operator_key: str) -> None:
        self.editor_page.add_operator_from_asset(side, operator_key)
        self.switchTo(self.editor_page)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self.editor_page.confirm_discard_changes("退出程序"):
            event.ignore()
            return

        super().closeEvent(event)
