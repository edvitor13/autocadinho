r"""Gera as capturas de tela da documentação (docs/img): o desenho de exemplo, uma planta de casa com
portas, janelas e louças, o menu de símbolos, a impressão e a janela de atualização.

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

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from autocadinho import FILE_EXT, fileio, geometry, i18n, printing, updater  # noqa: E402
from autocadinho.model import Beam, Dimension, Document, Ellipse, Line, Polygon, Rect, Symbol, Text  # noqa: E402
from autocadinho.ui import icons, prefs, theme  # noqa: E402

# Textos da planta da casa (é só uma captura: não entram no catálogo de traduções do app).
HOUSE_TEXT = {
    "pt_BR": {"title": "Casa (exemplo)", "plan": "Planta baixa", "entry": "Entrada", "garage": "GARAGEM",
              "rooms": ("SALA", "COZINHA", "QUARTO 1", "BANHEIRO", "QUARTO 2")},
    "en": {"title": "House (example)", "plan": "Floor plan", "entry": "Entrance", "garage": "GARAGE",
           "rooms": ("LIVING ROOM", "KITCHEN", "BEDROOM 1", "BATHROOM", "BEDROOM 2")},
}
NOTES = {
    "pt_BR": "\n".join(["## Novidades", "", "- Portas, janelas, escada, louças e o norte",
                        "- Círculo, triângulo e polígono, com a área em m²", "- Escolha da fonte dos textos",
                        "- Setas nas linhas"]),
    "en": "\n".join(["## What's new", "", "- Doors, windows, stairs, bathroom fixtures and north arrow",
                     "- Circle, triangle and polygon, with the area in m²", "- Choose the font of the texts",
                     "- Arrowheads on lines"]),
}


def house(lang: str) -> Document:
    """Planta de uma casa de 10,00 m × 8,00 m num terreno, com cômodos, portas, janelas e louças."""
    t = HOUSE_TEXT[lang]
    sep = "," if lang == "pt_BR" else "."
    doc = Document(title=t["title"])
    doc.add(Polygon(points=[[-450, -260], [1200, -200], [1250, 1000], [-450, 1000]], dashed=True, width=2,
                    show_lengths=True))
    walls = ((0, 0, 1000, 0), (1000, 0, 1000, 800), (0, 800, 1000, 800), (0, 0, 0, 800), (0, 450, 1000, 450),
             (550, 0, 550, 450), (420, 450, 420, 800), (650, 450, 650, 800))
    for x1, y1, x2, y2 in walls:
        doc.add(Beam(x1=x1, y1=y1, x2=x2, y2=y2, width=15, label=""))
    doc.add(Rect(x=560, y=8, w=170, h=55, width=2))  # bancada da cozinha
    rooms = ((275, 190, 550, 450), (775, 250, 450, 450), (210, 620, 420, 350), (535, 640, 230, 350),
             (825, 620, 350, 350))
    for name, (cx, cy, w, h) in zip(t["rooms"], rooms):
        doc.add(Text(x=cx, y=cy, text=name, size=24, bold=True))
        doc.add(Text(x=cx, y=cy + 36, text=geometry.format_area(w * h, sep), size=19))
    for shape, x, y, w, angle in (("door", 120, 0, 90, 0), ("door", 330, 450, 80, 0), ("door", 500, 450, 70, 0),
                                  ("door", 720, 450, 80, 0), ("door", 1000, 300, 80, 90),
                                  ("sliding", 550, 250, 150, 90), ("window", 380, 0, 200, 0),
                                  ("window", 830, 0, 150, 0), ("window", 210, 800, 150, 0),
                                  ("window", 535, 800, 60, 0), ("window", 825, 800, 150, 0)):
        doc.add(Symbol(shape=shape, x=x, y=y, w=w, angle=angle, wall=15))
    doc.add(Symbol(shape="sink", x=645, y=36, w=50, h=40))
    doc.add(Symbol(shape="toilet", x=470, y=758, w=40, h=65, angle=180))
    doc.add(Symbol(shape="sink", x=605, y=770, w=50, h=40, angle=180))
    doc.add(Symbol(shape="shower", x=602, y=498, w=80, h=80))
    doc.add(Symbol(shape="north", x=1110, y=-70, w=80, h=80))
    doc.add(Rect(x=-420, y=30, w=380, h=520, width=2, dashed=True, show_area=True))
    doc.add(Text(x=-230, y=230, text=t["garage"], size=24, bold=True))
    doc.add(Ellipse(x=1060, y=840, w=110, h=110, width=3, show_dims=True))
    doc.add(Line(x1=120, y1=-180, x2=120, y2=-30, width=3, arrow_end=True))
    doc.add(Text(x=245, y=-110, text=t["entry"], size=24, italic=True))
    doc.add(Text(x=400, y=-370, text=t["plan"], size=56, font="Segoe Script"))
    doc.add(Dimension(x1=0, y1=800, x2=1000, y2=800, offset=-90))
    doc.add(Dimension(x1=1000, y1=0, x2=1000, y2=800, offset=110))
    return doc


def grab_with_popup(win, popup):
    """Captura da janela com um menu flutuante (que é outra janela) desenhado por cima."""
    shot = win.grab()
    pos = popup.mapToGlobal(QPoint(0, 0)) - win.mapToGlobal(QPoint(0, 0))
    p = QPainter(shot)
    p.drawPixmap(pos, popup.grab())
    p.end()
    return shot


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
    # planta da casa: a porta da entrada selecionada mostra os ajustes do símbolo
    doc = house(lang)
    win.canvas.set_document(doc)
    app.processEvents()
    win.canvas.fit()
    door = next(el for el in doc.elements if el.kind == "symbol" and el.shape == "door")
    win.canvas.set_selection([door.id])
    app.processEvents()
    win.grab().save(str(out / f"planta{suffix}.png"))
    win.canvas.set_selection([])
    win.canvas.set_tool("symbol")
    fly = win.open_flyout("symbols")
    app.processEvents()
    grab_with_popup(win, fly).save(str(out / f"simbolos{suffix}.png"))
    fly.close()
    win.canvas.set_tool("select")
    # janela de atualização, como aparece para quem instalou pelo .msi
    from autocadinho.ui.update_dialog import UpdateDialog
    major, minor = (updater.current_version() + (0, 0))[:2]
    nxt = f"{major}.{minor + 1}.0"  # uma versão depois da atual
    name = f"Autocadinho-{nxt}-windows-x64.msi"
    rel = updater.Release(tag=f"v{nxt}", version=updater.parse_version(nxt), name=f"v{nxt}", body=NOTES[lang],
                          url="", published="", assets={name: ("https://example.invalid/" + name, 0)})
    real_info = updater.install_info
    updater.install_info = lambda: {"kind": "msi"}
    try:
        upd = UpdateDialog(win, rel)
    finally:
        updater.install_info = real_info
    upd.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    upd.resize(600, 470)
    upd.show()
    app.processEvents()
    upd.grab().save(str(out / f"atualizar{suffix}.png"))
    upd.close()
    win.open_example()
    app.processEvents()
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
