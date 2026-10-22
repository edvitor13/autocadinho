"""A janela de verdade, usada como uma pessoa usaria: mouse na área de desenho, painel, menus e arquivos.

As janelas são criadas com WA_DontShowOnScreen (existem e recebem eventos, mas não aparecem na tela)
e as caixas de pergunta são respondidas por `answer()`, que clica no botão pelo texto.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QMessageBox, QToolButton

from autocadinho import fileio, i18n, samples
from autocadinho.model import Beam, Dimension, Pillar, Text
from autocadinho.ui import prefs, theme
from autocadinho.ui.main_window import MainWindow

LEFT = Qt.MouseButton.LeftButton
NOMOD = Qt.KeyboardModifier.NoModifier


def make_window() -> MainWindow:
    w = MainWindow()
    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    w.resize(1400, 900)
    w.show()
    QApplication.processEvents()
    return w


@pytest.fixture
def win(qapp):
    w = make_window()
    yield w
    w._saved_state = w.history.current  # fecha sem perguntar
    w.close()
    w.deleteLater()
    QApplication.processEvents()


def answer(monkeypatch, text: str) -> list[str]:
    """Responde às próximas caixas de pergunta clicando no botão com esse texto. Devolve os títulos vistos."""
    seen: list[str] = []

    def fake_exec(box):
        seen.append(box.text())
        for b in box.buttons():
            if b.text() == text:
                b.click()
                return 0
        raise AssertionError(f"botão {text!r} não existe em {[b.text() for b in box.buttons()]}")
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return seen


def editor(w: MainWindow, doc=None) -> None:
    if doc is None:
        w.new_document()
    else:
        w._open_document(doc, None)
    QApplication.processEvents()
    w.canvas.fit()


def at(w: MainWindow, x: float, y: float) -> QPoint:
    q = w.canvas.to_screen((x, y))
    return QPoint(round(q.x()), round(q.y()))


def drag(w: MainWindow, a, b) -> None:
    c = w.canvas
    QTest.mousePress(c, LEFT, NOMOD, at(w, *a))
    QTest.mouseMove(c, at(w, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    QTest.mouseMove(c, at(w, *b))
    QTest.mouseRelease(c, LEFT, NOMOD, at(w, *b))


def click(w: MainWindow, p) -> None:
    QTest.mouseClick(w.canvas, LEFT, NOMOD, at(w, *p))


def beams(w):
    return [e for e in w.canvas.doc.elements if isinstance(e, Beam)]


# ------------------------------------------------------------------------------------- desenhar
def test_starts_on_home_and_new_drawing_opens_beam_tool(win):
    assert win.stack.currentIndex() == 0
    editor(win)
    assert win.stack.currentIndex() == 1
    assert win.canvas.tool == "beam"
    assert not win.is_dirty()
    assert win.windowTitle().startswith("Desenho sem título")


def test_draw_beam_by_dragging_snaps_and_names(win):
    editor(win)
    drag(win, (2, -3), (304, 9))  # torto e fora da grade: vira reta e encaixa de 10 em 10 cm
    (b,) = beams(win)
    assert (b.x1, b.y1, b.x2, b.y2) == (0, 0, 300, 0)
    assert b.label == "VIGA 1"
    assert win.canvas.selection == [b.id]
    assert win.is_dirty() and win.history.can_undo()
    drag(win, (300, 0), (300, 200))
    assert [x.label for x in beams(win)] == ["VIGA 1", "VIGA 2"]


def test_draw_beam_with_two_clicks(win):
    editor(win)
    click(win, (0, 100))
    assert not beams(win)  # ainda esperando o segundo clique
    click(win, (0, 400))
    (b,) = beams(win)
    assert (b.x1, b.y1, b.x2, b.y2) == (0, 100, 0, 400)


def test_tiny_drag_does_not_create_anything(win):
    editor(win)
    click(win, (100, 100))
    QTest.keyClick(win.canvas, Qt.Key.Key_Escape)
    assert not win.canvas.doc.elements
    assert not win.history.can_undo()


def test_pillars_snap_to_beam_ends_and_count_up(win):
    editor(win)
    drag(win, (0, 0), (500, 0))
    win.canvas.set_tool("pillar")
    click(win, (497, 4))
    click(win, (250, 3))
    pillars = [e for e in win.canvas.doc.elements if isinstance(e, Pillar)]
    assert [(p.x, p.y, p.label) for p in pillars] == [(500, 0, "P1"), (250, 0, "P2")]
    assert (pillars[0].w, pillars[0].h) == (40, 20)
    QTest.keyClick(win.canvas, Qt.Key.Key_R)  # próximo pilar em pé
    click(win, (0, 0))
    assert [(e.w, e.h) for e in win.canvas.doc.elements if isinstance(e, Pillar)][-1] == (20, 40)


def test_custom_and_empty_auto_names(win):
    editor(win)
    win.canvas.doc.beam_prefix = "PAREDE"
    drag(win, (0, 0), (300, 0))
    win.canvas.doc.beam_prefix = ""
    drag(win, (0, 200), (300, 200))
    assert [b.label for b in beams(win)] == ["PAREDE 1", ""]


def test_dimension_and_text_tools(win, monkeypatch):
    editor(win)
    win.canvas.set_tool("dim")
    drag(win, (0, 0), (350, 0))
    (d,) = [e for e in win.canvas.doc.elements if isinstance(e, Dimension)]
    assert d.length() == 350
    win.canvas.set_tool("text")
    click(win, (100, 300))
    ed = win.canvas._editor
    assert ed is not None
    ed.setText("Escada")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    (t,) = [e for e in win.canvas.doc.elements if isinstance(e, Text)]
    assert (t.text, t.x, t.y) == ("Escada", 100, 300)
    win.canvas.set_tool("text")
    click(win, (500, 300))
    QTest.keyClick(win.canvas._editor, Qt.Key.Key_Escape)  # texto vazio cancelado não fica no desenho
    assert len([e for e in win.canvas.doc.elements if isinstance(e, Text)]) == 1


def test_undo_redo_from_keyboard_and_buttons(win):
    editor(win)
    drag(win, (0, 0), (300, 0))
    drag(win, (0, 100), (300, 100))
    win._actions["undo"].trigger()
    assert len(beams(win)) == 1
    win.undo_btn.click()
    assert not beams(win)
    assert not win.is_dirty()
    win._actions["redo"].trigger()
    win.redo_btn.click()
    assert len(beams(win)) == 2


def test_select_move_and_nudge(win):
    editor(win)
    drag(win, (0, 0), (300, 0))
    win.canvas.set_tool("select")
    win.canvas.set_selection([])
    drag(win, (150, 0), (150, 205))  # arrasta pelo meio: o meio encaixa na grade
    (b,) = beams(win)
    assert (b.y1, b.y2) == (200, 200)
    QTest.keyClick(win.canvas, Qt.Key.Key_Right)
    QTest.keyClick(win.canvas, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert b.x1 == 110
    win.undo()
    assert beams(win)[0].x1 == 0  # as setas seguidas viram um passo só


def test_rubber_band_selection_and_delete(win):
    editor(win, samples.mezzanine())
    win.canvas.set_tool("select")
    drag(win, (-200, -200), (1300, 900))
    assert len(win.canvas.selection) == len(win.canvas.doc.elements)
    QTest.keyClick(win.canvas, Qt.Key.Key_Delete)
    assert not win.canvas.doc.elements
    win.undo()
    assert len(win.canvas.doc.elements) == 25


def test_eraser(win):
    editor(win)
    drag(win, (0, 0), (300, 0))
    win.canvas.set_tool("erase")
    click(win, (150, 0))
    assert not win.canvas.doc.elements


def test_double_click_renames_beam(win):
    editor(win)
    drag(win, (0, 0), (300, 0))
    win.canvas.set_tool("select")
    QTest.mouseDClick(win.canvas, LEFT, NOMOD, at(win, 150, 0))
    ed = win.canvas._editor
    assert ed is not None and ed.text() == "VIGA 1"
    ed.setText("VIGA BALDRAME")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    assert beams(win)[0].label == "VIGA BALDRAME"


def test_copy_paste_duplicate_rotate(win):
    editor(win)
    drag(win, (0, 0), (300, 0))
    win._actions["duplicate"].trigger()
    assert [b.label for b in beams(win)] == ["VIGA 1", "VIGA 2"]
    win._actions["copy"].trigger()
    win._actions["paste"].trigger()
    assert [b.label for b in beams(win)] == ["VIGA 1", "VIGA 2", "VIGA 3"]
    QTest.keyClick(win.canvas, Qt.Key.Key_R)
    b = beams(win)[-1]
    assert b.x1 == b.x2  # girou para a vertical


# ------------------------------------------------------------------------------------- painel
def test_panel_sets_exact_length_and_width(win):
    editor(win)
    drag(win, (0, 0), (300, 0))
    spins = win.panel.findChildren(QDoubleSpinBox)
    length, width = spins[0], spins[1]
    assert length.value() == 3.0 and length.suffix() == " m"
    length.setValue(4.25)
    width.setValue(20)
    b = beams(win)[0]
    assert b.length() == pytest.approx(425) and b.width == 20
    win.undo()  # campos diferentes do painel são passos diferentes
    b = beams(win)[0]
    assert b.width == 15 and b.length() == pytest.approx(425)
    win.undo()
    assert beams(win)[0].length() == pytest.approx(300)


def test_panel_color_buttons(win):
    editor(win)
    drag(win, (0, 0), (300, 0))
    swatches = [b for b in win.panel.findChildren(QToolButton) if b.objectName() == "Swatch"]
    swatches[1].click()  # vermelho
    assert beams(win)[0].color == "#d64541"


def test_document_settings_without_selection(win):
    from PySide6.QtWidgets import QLabel, QLineEdit
    editor(win)
    drag(win, (0, 0), (300, 0))
    win.canvas.set_selection([])
    kickers = [lab.text() for lab in win.panel.findChildren(QLabel) if lab.objectName() == "Kicker"]
    assert "NOMES AUTOMÁTICOS" in kickers
    prefix = next(e for e in win.panel.findChildren(QLineEdit) if e.text() == "VIGA")
    prefix.setFocus()
    prefix.selectAll()
    QTest.keyClicks(prefix, "MURO")
    assert win.canvas.doc.beam_prefix == "MURO"
    win.panel._set_doc("unit", "cm", rebuild=True)
    assert win.canvas.doc.unit == "cm"
    win.canvas.set_selection([beams(win)[0].id])
    assert win.panel.findChildren(QDoubleSpinBox)[0].suffix() == " cm"


# ------------------------------------------------------------------------------------- arquivos
def test_save_open_and_recent(win, tmp_path, monkeypatch):
    editor(win)
    drag(win, (0, 0), (300, 0))
    path = tmp_path / "obra.cadinho"
    assert win._save_to(str(path))
    assert not win.is_dirty()
    assert win.canvas.doc.title == "obra"  # sem título, ganha o nome do arquivo
    assert prefs.recent_files()[0].endswith("obra.cadinho")
    assert fileio.read_thumbnail(path)[:4] == b"\x89PNG"
    win.new_document()
    assert not beams(win)
    assert win.open_path(str(path))
    assert beams(win)[0].label == "VIGA 1"
    assert win.path.endswith("obra.cadinho")
    win.show_home()
    cards = [b for b in win.home.findChildren(QToolButton) if b.objectName() == "Recent"]
    assert len(cards) == 1


def test_open_errors_are_reported(win, tmp_path, monkeypatch):
    bad = tmp_path / "ruim.cadinho"
    bad.write_text("isto não é um desenho", encoding="utf-8")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: shown.append(a[2]))
    assert not win.open_path(str(bad))
    assert not win.open_path(str(tmp_path / "sumiu.cadinho"))
    assert "não é um desenho" in shown[0]
    assert "não foi encontrado" in shown[1]


def test_unsaved_changes_prompt(win, monkeypatch):
    editor(win)
    drag(win, (0, 0), (300, 0))
    seen = answer(monkeypatch, "Cancelar")
    win.new_document()
    assert len(beams(win)) == 1 and seen
    answer(monkeypatch, "Não salvar")
    win.new_document()
    assert not beams(win)


def test_recovery_after_power_cut(qapp, monkeypatch):
    first = make_window()
    editor(first)
    drag(first, (0, 0), (300, 0))
    first._write_recovery()
    assert fileio.read_recovery() is not None
    first.deleteLater()  # sem fechar: como se a energia tivesse caído
    QApplication.processEvents()
    second = make_window()
    try:
        answer(monkeypatch, "Recuperar")
        second.startup([])
        assert second.stack.currentIndex() == 1
        assert [b.label for b in beams(second)] == ["VIGA 1"]
        assert second.is_dirty() and second.path is None
    finally:
        second._saved_state = second.history.current
        second.close()
    assert fileio.read_recovery() is None  # fechar normalmente apaga a cópia


def test_recovery_can_be_discarded(qapp, monkeypatch):
    fileio.write_recovery(samples.mezzanine(), None)
    w = make_window()
    try:
        answer(monkeypatch, "Descartar")
        w.startup([])
        assert w.stack.currentIndex() == 0
        assert fileio.read_recovery() is None
    finally:
        w.close()


# ------------------------------------------------------------------------------------- aparência
def test_language_switch_keeps_the_drawing(win):
    editor(win, samples.mezzanine())
    n = len(win.canvas.doc.elements)
    win.set_language("en")
    assert i18n.language() == "en"
    assert win.stack.currentIndex() == 1
    assert len(win.canvas.doc.elements) == n
    assert win._tool_buttons["beam"].text() == "Beam"
    assert prefs.settings().value("language") == "en"
    win.set_language("pt_BR")
    assert win._tool_buttons["beam"].text() == "Viga"


def test_theme_switch(win):
    win.toggle_theme()
    assert theme.is_dark() and prefs.settings().value("theme") == "dark"
    win.toggle_theme()
    assert not theme.is_dark()


def test_print_dialog_suggests_a_scale_that_fits(win):
    from autocadinho.ui.print_dialog import PrintDialog, load_options
    editor(win, samples.mezzanine())
    dlg = PrintDialog(win, win.canvas.doc, "x")
    dlg.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dlg.show()
    dlg.scale.setCurrentIndex(dlg.scale.findData(20))
    assert not dlg.warn.isHidden()
    assert "1:50" in dlg.fix_btn.text()
    dlg.fix_btn.click()
    assert dlg.opts.scale == 50 and dlg.warn.isHidden()
    assert load_options().scale == 50  # a escolha fica guardada
    dlg.paper.setCurrentIndex(dlg.paper.findData("Oficio"))
    assert load_options().paper == "Oficio"
    dlg.close()


def test_help_and_about_build(win, monkeypatch):
    from autocadinho.ui.help_dialog import HelpDialog, help_html
    assert "Começando" in help_html()
    HelpDialog(win).close()
    shown = []
    monkeypatch.setattr(QMessageBox, "about", lambda *a: shown.append(a[2]))
    win.show_about()
    assert "MIT" in shown[0]


def test_self_test_report(win, tmp_path):
    """A autoverificação que o CI roda no executável empacotado (AUTOCADINHO_SELFTEST)."""
    import json

    from autocadinho.app import self_test
    i18n.set_language("pt_BR")  # instala a tradução do próprio Qt (precisa da QApplication)
    out = tmp_path / "relatorio.json"
    self_test(win, str(out))
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["ok"], r
    assert r["elements"] == len(samples.mezzanine().elements)
    assert r["pdf"] > 1000 and r["png"] > 1000
    assert r["en"] == "Beam" and r["qt_pt_BR"] == "&Desfazer"
