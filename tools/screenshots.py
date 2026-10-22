r"""Gera as capturas de tela da documentação (docs/img) com o desenho de exemplo.

Uso:  .venv\Scripts\python tools\screenshots.py [pasta]   (padrão: docs/img)

Roda com preferências e pasta de dados temporárias: não mexe nas configurações de quem usa o app.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp(prefix="autocadinho-shots-")
os.environ["AUTOCADINHO_SETTINGS_DIR"] = os.path.join(_tmp, "settings")
os.environ["AUTOCADINHO_DATA_DIR"] = os.path.join(_tmp, "data")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from autocadinho import FILE_EXT, fileio, i18n, printing  # noqa: E402
from autocadinho.ui import icons, prefs, theme  # noqa: E402


def shoot(out: Path, lang: str = "pt_BR") -> None:
    from autocadinho.ui.main_window import MainWindow
    from autocadinho.ui.print_dialog import PrintDialog
    i18n.set_language(lang)
    suffix = "" if lang == "pt_BR" else "-en"
    win = MainWindow()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)  # não aparece na tela de quem roda
    win.resize(1440, 880)
    win.show()
    app = QApplication.instance()
    # um desenho salvo, para a tela inicial ter um recente com miniatura
    from autocadinho import samples
    doc = samples.mezzanine()
    saved = os.path.join(_tmp, (doc.title or "exemplo") + FILE_EXT)
    fileio.save(doc, saved, printing.thumbnail_png(doc))
    prefs.add_recent(saved)
    win.show_home()
    app.processEvents()
    win.grab().save(str(out / f"inicio{suffix}.png"))
    win.open_example()
    app.processEvents()
    win.canvas.fit()
    beam = next(el for el in win.canvas.doc.elements if el.kind == "beam" and el.label.endswith(" 8"))
    win.canvas.set_selection([beam.id])
    app.processEvents()
    win.grab().save(str(out / f"desenho{suffix}.png"))
    win.set_theme("dark")
    app.processEvents()
    win.grab().save(str(out / f"desenho-escuro{suffix}.png"))
    win.set_theme("light")
    win.canvas.set_selection([])
    dlg = PrintDialog(win, win.canvas.doc, os.path.join(_tmp, "x"))
    dlg.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dlg.resize(1100, 720)
    dlg.show()
    app.processEvents()
    dlg.grab().save(str(out / f"imprimir{suffix}.png"))
    dlg.close()
    win.history.reset(win._state())
    win._saved_state = win.history.current
    win.close()


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "img"
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    theme.set_theme("light")
    app.setFont(theme.font(10))
    theme.apply(app)
    app.setWindowIcon(icons.app_icon())
    for lang in ("pt_BR", "en"):
        shoot(out, lang)
    print("capturas em", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
