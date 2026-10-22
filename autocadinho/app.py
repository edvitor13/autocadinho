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


def self_test(win, out: str) -> None:
    """Conferência do executável empacotado, usada pelo CI (packaging/windows/verificar_exe.ps1).

    Com AUTOCADINHO_SELFTEST=relatorio.json, o app abre o desenho de exemplo, gera um PDF e uma imagem,
    confere as traduções (a do app e a do próprio Qt), grava o relatório em JSON e fecha sozinho.
    """
    import json
    import tempfile

    from PySide6.QtCore import QCoreApplication

    from . import printing
    report: dict = {"version": __version__}
    try:
        win.open_example()
        doc = win.canvas.doc
        report["elements"] = len(doc.elements)
        opts = printing.PageOptions()
        with tempfile.TemporaryDirectory(prefix="autocadinho-selftest-") as folder:
            pdf, png = os.path.join(folder, "teste.pdf"), os.path.join(folder, "teste.png")
            report["pdf"] = printing.save_pdf(doc, opts, pdf) and os.path.getsize(pdf)
            report["png"] = printing.save_png(doc, opts, png, dpi=72) and os.path.getsize(png)
        report["qt_pt_BR"] = QCoreApplication.translate("QLineEdit", "&Undo")
        i18n.set_language("en")
        report["en"] = i18n._("Viga")
        report["ok"] = True
    except Exception as e:  # noqa: BLE001 (o relatório diz o que falhou)
        report["ok"] = False
        report["error"] = repr(e)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    QApplication.instance().exit(0 if report["ok"] else 1)


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
    test_report = os.environ.get("AUTOCADINHO_SELFTEST")
    i18n.set_language("pt_BR" if test_report else choose_language(settings))
    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    if test_report:
        QTimer.singleShot(0, lambda: self_test(win, test_report))
        return app.exec()
    files = [a for a in sys.argv[1:] if os.path.isfile(a)]
    QTimer.singleShot(0, lambda: win.startup(files))
    return app.exec()
