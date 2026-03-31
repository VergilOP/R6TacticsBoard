from __future__ import annotations

import faulthandler
import sys
import traceback
from datetime import datetime
from pathlib import Path
from threading import Lock

from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

from r6_tactics_board.infrastructure.assets.asset_paths import PROJECT_ROOT


_LOG_DIR = PROJECT_ROOT / ".tmp" / "logs"
_RUNTIME_LOG = _LOG_DIR / "runtime.log"
_CRASH_LOG = _LOG_DIR / "crash.log"
_runtime_handle = None
_crash_handle = None
_install_lock = Lock()
_installed = False


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_line(message: str) -> None:
    global _runtime_handle
    if _runtime_handle is None:
        return
    _runtime_handle.write(f"[{_timestamp()}] {message}\n")
    _runtime_handle.flush()


def debug_log(message: str) -> None:
    try:
        _write_line(message)
    except Exception:
        pass


def install_runtime_debug_logging() -> None:
    global _installed, _runtime_handle, _crash_handle
    with _install_lock:
        if _installed:
            return

        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _runtime_handle = _RUNTIME_LOG.open("a", encoding="utf-8", newline="\n")
        _crash_handle = _CRASH_LOG.open("a", encoding="utf-8", newline="\n")
        faulthandler.enable(file=_crash_handle, all_threads=True)

        previous_excepthook = sys.excepthook

        def _log_excepthook(exc_type, exc_value, exc_traceback):
            debug_log("Unhandled Python exception:")
            formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)).rstrip()
            for line in formatted.splitlines():
                debug_log(line)
            previous_excepthook(exc_type, exc_value, exc_traceback)

        def _qt_message_handler(message_type, context, message):
            level_map = {
                QtMsgType.QtDebugMsg: "QT_DEBUG",
                QtMsgType.QtInfoMsg: "QT_INFO",
                QtMsgType.QtWarningMsg: "QT_WARNING",
                QtMsgType.QtCriticalMsg: "QT_CRITICAL",
                QtMsgType.QtFatalMsg: "QT_FATAL",
            }
            level = level_map.get(message_type, "QT")
            location = ""
            if context is not None and context.file:
                location = f" ({Path(context.file).name}:{context.line})"
            debug_log(f"{level}{location}: {message}")

        sys.excepthook = _log_excepthook
        qInstallMessageHandler(_qt_message_handler)
        debug_log("Runtime debug logging enabled")
        _installed = True


def install_qfluent_theme_debug_logging() -> None:
    try:
        from qfluentwidgets.common import style_sheet as qss_module
    except Exception:
        return

    if getattr(qss_module, "_r6tb_theme_debug_installed", False):
        return

    original_set_style_sheet = qss_module.setStyleSheet
    original_update_style_sheet = qss_module.updateStyleSheet

    def _describe_widget(widget) -> str:
        try:
            object_name = widget.objectName() or "-"
        except Exception:
            object_name = "-"
        try:
            visible = widget.isVisible()
        except Exception:
            visible = "?"
        return f"{widget.__class__.__name__}(objectName={object_name}, visible={visible})"

    def _logged_set_style_sheet(widget, source, theme=qss_module.Theme.AUTO, register=True):
        debug_log(f"qfluent: setStyleSheet start -> {_describe_widget(widget)}")
        result = original_set_style_sheet(widget, source, theme, register)
        debug_log(f"qfluent: setStyleSheet done -> {_describe_widget(widget)}")
        return result

    def _logged_update_style_sheet(lazy=False):
        debug_log(f"qfluent: updateStyleSheet start lazy={lazy}")
        result = original_update_style_sheet(lazy)
        debug_log("qfluent: updateStyleSheet done")
        return result

    qss_module.setStyleSheet = _logged_set_style_sheet
    qss_module.updateStyleSheet = _logged_update_style_sheet
    qss_module._r6tb_theme_debug_installed = True
    debug_log("QFluentWidgets theme debug logging enabled")
