"""Formas (círculo, triângulo, polígono), símbolos (porta, janela...), setas, área e fontes.

Modelo e pintura sem janela; no fim, as ferramentas usadas na janela de verdade, com o mouse.
"""

from __future__ import annotations

import json
import math

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from autocadinho import geometry as geo
from autocadinho import render
from autocadinho.model import SYMBOLS, Beam, Document, Ellipse, Line, Polygon, Rect, Symbol, Text
from test_ui import LEFT, NOMOD, at, click, drag, editor, make_window


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


@pytest.fixture
def win(qapp):
    w = make_window()
    yield w
    w._saved_state = w.history.current
    w.close()
    w.deleteLater()
    QApplication.processEvents()


def shapes(w, cls):
    return [e for e in w.canvas.doc.elements if isinstance(e, cls)]


# ------------------------------------------------------------------------------------- geometria
def test_area_and_polygon_math():
    square = [(0, 0), (200, 0), (200, 100), (0, 100)]
    assert geo.polygon_area(square) == 20000  # sentido horário na tela: positiva
    assert geo.polygon_area(list(reversed(square))) == -20000
    assert geo.polygon_centroid(square) == (100, 50)
    assert geo.point_in_polygon((50, 50), square) and not geo.point_in_polygon((250, 50), square)
    assert geo.format_area(20000) == "2,00 m²"
    assert geo.format_area(125000, ".") == "12.50 m²"
    pts = geo.ellipse_points(0, 0, 10, 5, 4)
    assert pts[0] == (10, 0) and abs(pts[1][1] - 5) < 1e-9


# ------------------------------------------------------------------------------------- modelo
def test_new_elements_round_trip_and_old_files_still_open():
    doc = Document(font="Georgia")
    doc.add(Ellipse(x=0, y=0, w=100, h=100, fill=True, show_area=True))
    doc.add(Polygon(points=[[0, 0], [300, 0], [150, 200]], show_lengths=True))
    doc.add(Symbol(shape="window", x=10, y=20, w=120, angle=90, wall=15, label="J1"))
    doc.add(Line(x1=0, y1=0, x2=100, y2=0, arrow_end=True))
    doc.add(Text(text="Oi", font="Arial", italic=True))
    data = json.loads(json.dumps(doc.to_dict()))
    again = Document.from_dict(data)
    assert again.to_dict() == doc.to_dict()
    assert again.font == "Georgia"
    # Arquivo da 1.0 (sem os campos novos): tudo no padrão neutro.
    old = Document.from_dict({"elements": [{"kind": "text", "text": "x"}, {"kind": "line", "x2": 10},
                                           {"kind": "rect"}]})
    t, ln, r = old.elements
    assert (old.font, t.font, t.italic, ln.arrow_start, ln.arrow_end, r.show_area) == ("", "", False, False, False,
                                                                                       False)


def test_bad_polygon_points_are_dropped():
    doc = Document.from_dict({"elements": [{"kind": "poly", "points": [[0, 0], ["x", 1], [5], "lixo",
                                                                         [10, float("nan")], [10, 0], [0, 10]]},
                                           {"kind": "poly", "points": "nada"}]})
    (a,) = doc.elements  # o segundo, sem nenhum ponto, não tem como ser usado
    assert a.points == [[0, 0], [10, 0], [0, 10]]


def test_polygon_names_area_and_perimeter():
    tri = Polygon(points=[[0, 0], [300, 0], [0, 400]])
    assert tri.name_key() == "Triângulo"
    assert tri.area() == 60000 and tri.perimeter() == 1200
    quad = Polygon(points=[[0, 0], [100, 0], [100, 100], [0, 100]])
    assert quad.name_key() == "Polígono" and len(quad.sides()) == 4
    quad.closed = False
    assert quad.name_key() == "Linha com pontos" and len(quad.sides()) == 3 and quad.area() == 0
    quad.rotate90((0, 0))
    assert quad.points[1] == [0, 100]
    quad.move(5, 5)
    assert quad.points[0] == [5, 5]


def test_ellipse_circle_and_snap_outline():
    c = Ellipse(x=0, y=0, w=100, h=100)
    assert c.is_circle() and c.name_key() == "Círculo"
    assert math.isclose(c.area(), math.pi * 2500)
    assert (50, 0) in c.key_points() and len(c.snap_segments()) == 48
    c.h = 60
    assert c.name_key() == "Elipse"


def test_symbol_local_frame_rotation_and_flips():
    s = Symbol(shape="door", x=100, y=50, w=80, angle=90, flip_x=True, flip_y=True)
    for q in ((10, 20), (-30, 5)):
        back = s.to_local(s.to_world(*q))
        assert math.isclose(back[0], q[0], abs_tol=1e-9) and math.isclose(back[1], q[1], abs_tol=1e-9)
    s = Symbol(shape="door", x=0, y=0, w=80)
    assert s.local_bounds() == (-40, 0, 40, 80)
    assert s.center() == (0, 40)
    s.rotate90((0, 0))
    assert s.angle == 90 and s.center() == pytest.approx((-40, 0))
    assert Symbol(shape="stairs", w=300).step_count() == 11
    assert Symbol(shape="stairs", w=300, steps=5).step_count() == 5
    assert set(SYMBOLS) >= {"door", "door2", "sliding", "window", "stairs", "toilet", "sink", "shower", "north"}
    assert Symbol(shape="door").name_key() == "Porta"


# ------------------------------------------------------------------------------------- pintura
def paint(doc: Document, size=(400, 200), scale=1.0, origin=(0, 0)) -> QImage:
    img = QImage(*size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.translate(*origin)
    p.scale(scale, scale)
    render.paint_document(p, doc, render.print_style())
    p.end()
    return img


def test_door_opens_the_wall_even_when_drawn_before_it():
    doc = Document()
    door = doc.add(Symbol(shape="door", x=200, y=50, w=80, wall=20))
    doc.add(Beam(x1=0, y1=50, x2=400, y2=50, width=20, label=""))
    assert render.paint_order(doc)[-1] is door
    img = paint(doc)
    assert img.pixelColor(100, 50).lightness() < 60  # parede
    assert img.pixelColor(200, 50).lightness() > 200  # vão aberto, cor do papel
    door.wall = 0
    assert paint(doc).pixelColor(200, 50).lightness() < 60  # sem espessura: não abre


def test_every_new_kind_paints_hits_and_has_bounds():
    doc = Document()
    els = [Ellipse(x=0, y=0, w=100, h=100, fill=True, show_dims=True, show_area=True),
           Polygon(points=[[200, 0], [300, 0], [250, 90]], fill=True, show_lengths=True, show_area=True),
           Line(x1=0, y1=150, x2=200, y2=150, arrow_start=True, arrow_end=True),
           Text(x=350, y=150, text="Fonte", font="Courier New", italic=True)]
    els += [Symbol(shape=s, x=100 + 120 * i, y=300, w=w, h=h, wall=15) for i, (s, (_n, w, h)) in
            enumerate(SYMBOLS.items())]
    for el in els:
        doc.add(el)
    img = paint(doc, (800, 300), 0.6, (20, 40))
    assert img.pixelColor(2, 2).name() == "#ffffff"
    for el in els:
        r = render.element_bounds(el, doc)
        assert r.width() > 0 and r.height() > 0, el.kind
        found = render.hit(doc, el.center() if not isinstance(el, Polygon) else (250, 0), 2)
        assert found is not None, el.kind
    assert render.area_box(els[0], doc)[0] == "0,79 m²"
    assert [t for t, _b in render.poly_length_boxes(els[1], doc)][0] == "1,00 m"
    assert render.rect_dim_boxes(els[0], doc)[0][0] == "Ø 1,00 m"


def test_lengths_of_a_closed_polygon_go_outside():
    doc = Document()
    for pts in ([[0, 0], [100, 0], [100, 100], [0, 100]], [[0, 0], [0, 100], [100, 100], [100, 0]]):
        el = Polygon(points=pts, show_lengths=True)
        for (_t, box), (a, b) in zip(render.poly_length_boxes(el, doc), el.sides()):
            assert not geo.point_in_polygon((box.cx, box.cy), el.pts())


def test_fonts_change_text_size():
    assert render.family_of("") == render.font_family()
    a = render.text_extent("Autocadinho 123", 10, family="Courier New")
    b = render.text_extent("Autocadinho 123", 10, family="Arial")
    assert a != b


def test_handles_resize_shapes_and_symbols():
    doc = Document()
    poly = Polygon(points=[[0, 0], [100, 0], [50, 80]])
    render.apply_handle(poly, "v2", (50, 120))
    assert poly.points[2] == [50, 120]
    ell = Ellipse(x=0, y=0, w=100, h=100)
    render.apply_handle(ell, "br", (200, 50), render.handle_anchor(ell, "br"))
    assert (ell.x, ell.y, ell.w, ell.h) == (0, 0, 200, 50)
    door = Symbol(shape="door", x=0, y=0, w=80, angle=90)
    names = [n for n, _p in render.handles(door, doc)]
    assert names == ["j1", "j2"]
    render.apply_handle(door, "j2", door.to_world(60, 0))
    assert door.w == pytest.approx(120)
    sink = Symbol(shape="sink", w=50, h=40)
    render.apply_handle(sink, "sy", (0, 35))
    assert sink.h == 70


def test_wall_at_finds_beams_and_their_direction():
    doc = Document()
    doc.add(Beam(x1=0, y1=0, x2=500, y2=0, width=20))
    doc.add(Beam(x1=600, y1=400, x2=600, y2=0, width=12))
    q, ang, thick, _seg = render.wall_at(doc, (203, 9), 5)
    assert (q, ang, thick) == ((203, 0), 0, 20)
    q, ang, thick, _seg = render.wall_at(doc, (604, 100), 5)
    assert (q, ang, thick) == ((600, 100), 90, 12)
    assert render.wall_at(doc, (300, 200), 5) is None


# ------------------------------------------------------------------------------------- na janela
def test_flyouts_choose_shapes_and_symbols(win):
    editor(win)
    fly = win.open_flyout("shapes")
    assert set(fly.buttons) == {"rect", "ellipse", "triangle", "poly"}
    fly.buttons["ellipse"].click()
    QApplication.processEvents()
    assert win.canvas.tool == "ellipse"
    assert win._tool_buttons["shapes"].isChecked()
    assert win._flyout is None
    fly = win.open_flyout("symbols")
    assert list(fly.buttons) == list(SYMBOLS)
    fly.buttons["window"].click()
    QApplication.processEvents()
    assert (win.canvas.tool, win.canvas.symbol_shape) == ("symbol", "window")
    assert win._tool_buttons["symbols"].isChecked()
    fly = win.open_flyout("shapes")
    fly.close()  # fechou sem escolher: continua nos símbolos
    QApplication.processEvents()
    assert win._tool_buttons["symbols"].isChecked() and win.canvas.tool == "symbol"


def test_draw_circle_and_triangle(win):
    editor(win)
    win.canvas.set_tool("ellipse")
    drag(win, (0, 0), (150, 100))
    (e,) = shapes(win, Ellipse)
    assert (e.x, e.y, e.w, e.h) == (0, 0, 150, 100)
    win.canvas.set_tool("triangle")
    drag(win, (300, 0), (500, 200))
    (t,) = shapes(win, Polygon)
    assert t.points == [[300, 200], [400, 0], [500, 200]] and t.name_key() == "Triângulo"
    assert win.canvas.selection == [t.id]


def test_polygon_point_by_point(win):
    editor(win)
    win.canvas.set_tool("poly")
    for p in ((0, 0), (400, 0), (400, 300)):
        click(win, p)
    QTest.keyClick(win.canvas, Qt.Key.Key_Backspace)  # desfaz o último canto
    click(win, (400, 200))
    click(win, (0, 200))
    assert not shapes(win, Polygon)  # ainda desenhando
    click(win, (1, 1))  # no primeiro ponto: fecha
    (p,) = shapes(win, Polygon)
    assert p.points == [[0, 0], [400, 0], [400, 200], [0, 200]]
    assert p.closed and p.area() == 80000
    # Com Enter também termina; com menos de 3 pontos, nada é criado.
    click(win, (600, 0))
    click(win, (800, 0))
    QTest.keyClick(win.canvas, Qt.Key.Key_Return)
    assert len(shapes(win, Polygon)) == 1
    for q in ((600, 0), (800, 0), (800, 100)):
        click(win, q)
    QTest.keyClick(win.canvas, Qt.Key.Key_Return)
    assert len(shapes(win, Polygon)) == 2
    win.undo()
    assert len(shapes(win, Polygon)) == 1


def test_door_snaps_into_the_wall(win):
    editor(win)
    drag(win, (0, 0), (500, 0))
    drag(win, (500, 0), (500, 400))
    win.canvas.set_symbol("door")
    assert win.canvas.tool == "symbol"
    QTest.mouseMove(win.canvas, at(win, 203, 6))
    click(win, (203, 6))
    (d,) = shapes(win, Symbol)
    assert (d.x, d.y, d.angle, d.wall) == (200, 0, 0, 15)
    QTest.keyClick(win.canvas, Qt.Key.Key_R)  # vira o lado da próxima porta
    QTest.mouseMove(win.canvas, at(win, 496, 151))
    click(win, (496, 151))
    d2 = shapes(win, Symbol)[-1]
    assert (d2.x, d2.y, d2.angle, d2.wall) == (500, 150, 270, 15)
    win.canvas.set_symbol("north")
    click(win, (800, 800))
    n = shapes(win, Symbol)[-1]
    assert (n.shape, n.x, n.y, n.wall) == ("north", 800, 800, 0)


def test_panel_changes_fonts(win):
    from autocadinho.ui.properties import _FontCombo, font_families
    editor(win)
    popular, others = font_families()
    family = (popular + others)[0]
    combo = win.panel.findChild(_FontCombo)  # sem seleção: a fonte do desenho
    combo.fill()
    combo.setCurrentIndex(combo.findData(family))
    assert win.canvas.doc.font == family
    t = win.canvas.doc.add(Text(x=0, y=0, text="Oi"))
    win.commit("add")
    win.canvas.set_selection([t.id])
    QApplication.processEvents()
    combo = win.panel.findChild(_FontCombo)
    assert combo.currentData() == ""  # a mesma do desenho
    combo.fill()
    combo.setCurrentIndex(combo.findData(family))
    assert t.font == family
    win.undo()
    assert win.canvas.doc.get(t.id).font == ""


def test_panel_for_symbol_and_circle(win):
    from PySide6.QtWidgets import QCheckBox
    editor(win)
    s = win.canvas.doc.add(Symbol(shape="door", wall=15))
    win.canvas.set_selection([s.id])
    QApplication.processEvents()
    boxes = {b.text(): b for b in win.panel.findChildren(QCheckBox)}
    boxes["Abre para o outro lado"].click()
    assert win.canvas.doc.get(s.id).flip_y
    c = win.canvas.doc.add(Ellipse(x=0, y=0, w=100, h=60))
    win.canvas.set_selection([c.id])
    QApplication.processEvents()
    boxes = {b.text(): b for b in win.panel.findChildren(QCheckBox)}
    boxes["Círculo perfeito"].click()
    c = win.canvas.doc.get(c.id)
    assert (c.w, c.h, c.center()) == (100, 100, (50, 30))


def test_reading_skips_unusable_shapes_and_fixes_sizes():
    doc = Document.from_dict({"elements": [
        {"kind": "symbol", "shape": "banheira", "w": 100},  # de uma versão mais nova
        {"kind": "poly", "points": [[0, 0]]},
        {"kind": "poly", "points": "lixo"},
        {"kind": "symbol", "shape": "stairs", "w": -5, "h": 0, "wall": -1, "steps": -3},
        {"kind": "poly", "points": [[0, 0], [100, 0]], "closed": False},
    ]})
    assert [el.kind for el in doc.elements] == ["symbol", "poly"]
    stairs = doc.elements[0]
    assert (stairs.w, stairs.h, stairs.wall, stairs.steps) == (1.0, 1.0, 0.0, 0)
    assert stairs.step_count() >= 2
