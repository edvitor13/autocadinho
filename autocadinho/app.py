"""Ponto de entrada do aplicativo."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from . import APP_NAME, __version__, i18n
from .ui import icons, prefs, theme


def choose_language(settings: QSettings) -> str:
    """Idioma salvo ou, no primeiro acesso, o escolhido na janela de idiomas."""
    saved = str(settings.value("language", "") or "")
    if saved in i18n.LANGUAGES:
        return saved
    from .ui.language_dialog import LanguageDialog
    dlg = LanguageDialog(None, i18n.system_language())
    dlg.exec()
    settings.setValue("language", dlg.selected)
    return dlg.selected


def main() -> int:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Autocadinho.App")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    settings = prefs.settings()
    theme.set_theme(str(settings.value("theme", "light") or "light"))
    app.setFont(theme.font(10))
    theme.apply(app)
    app.setWindowIcon(icons.app_icon())
    i18n.set_language(choose_language(settings))
    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    files = [a for a in sys.argv[1:] if os.path.isfile(a)]
    QTimer.singleShot(0, lambda: win.startup(files))
    return app.exec()
