import json

import pytest
from PySide6.QtCore import QRectF

from autocadinho import printing, render, samples
from autocadinho.model import Beam, Dimension, Document, Line, Pillar, Rect, Text
from autocadinho.printing import PageOptions


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


# ------------------------------------------------------------------------------------- nomes e caixas
def test_beam_label_goes_above_horizontal_and_left_of_vertical():
    doc = Document()
    h = doc.add(Beam(x1=0, y1=0, x2=400, y2=0, label="VIGA 1"))
    v = doc.add(Beam(x1=0, y1=0, x2=0, y2=400, label="VIGA 2"))
    bh = render.label_box(h, doc)
    bv = render.label_box(v, doc)
    assert bh.cx == pytest.approx(200) and bh.cy + bh.h / 2 < -h.width / 2
    assert bv.cy == pytest.approx(200) and bv.cx + bv.w / 2 < -v.width / 2


def test_hidden_or_empty_label_has_no_box():
    doc = Document()
    b = doc.add(Beam(x1=0, y1=0, x2=100, y2=0, label="VIGA 1", label_visible=False))
    assert render.label_box(b, doc) is None
    b.label_visible, b.label = True, "  "
    assert render.label_box(b, doc) is None


def test_materialize_label_keeps_the_position():
    doc = Document()
    p = doc.add(Pillar(x=100, y=100, w=40, h=20, label="P1"))
    before = render.label_box(p, doc)
    render.materialize_label(p, doc)
    after = render.label_box(p, doc)
    assert p.label_dx is not None
    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy))


def test_hit_prefers_front_and_labels():
    doc = Document()
    back = doc.add(Beam(x1=0, y1=0, x2=400, y2=0, label="VIGA 1"))
    front = doc.add(Pillar(x=200, y=0, w=40, h=40, label="P1"))
    assert render.hit(doc, (200, 0), 1) == (front.id, "body")
    assert render.hit(doc, (50, 0), 1) == (back.id, "body")
    box = render.label_box(back, doc)
    assert render.hit(doc, (box.cx, box.cy), 1) == (back.id, "label")
    assert render.hit(doc, (1000, 1000), 1) is None


def test_hit_on_other_kinds():
    doc = Document()
    r = doc.add(Rect(x=0, y=0, w=100, h=100))
    t = doc.add(Text(x=500, y=500, text="Escada", size=20))
    d = doc.add(Dimension(x1=0, y1=300, x2=200, y2=300, offset=-50))
    assert render.hit(doc, (50, 50), 1) is None  # retângulo vazio: só a borda
    assert render.hit(doc, (0, 50), 1) == (r.id, "body")
    r.fill = True
    assert render.hit(doc, (50, 50), 1) == (r.id, "body")
    assert render.hit(doc, (500, 500), 1) == (t.id, "body")
    assert render.hit(doc, (100, 350), 1) == (d.id, "body")  # na linha de cota (afastada para baixo)


def test_touching_selects_by_area():
    doc = Document()
    b = doc.add(Beam(x1=0, y1=0, x2=400, y2=0))
    p = doc.add(Pillar(x=600, y=600))
    assert render.touching(doc, QRectF(100, -20, 50, 40)) == [b.id]
    assert set(render.touching(doc, QRectF(-50, -50, 800, 800))) == {b.id, p.id}


def test_handles_and_apply_handle():
    doc = Document()
    b = doc.add(Line(x1=0, y1=0, x2=100, y2=0))
    assert [n for n, _p in render.handles(b, doc)] == ["p1", "p2"]
    render.apply_handle(b, "p2", (250, 0))
    assert b.length() == 250
    r = doc.add(Rect(x=0, y=0, w=100, h=50))
    anchor = render.handle_anchor(r, "br")
    render.apply_handle(r, "br", (-20, -10), anchor)
    assert (r.x, r.y, r.w, r.h) == (-20, -10, 20, 10)
    d = doc.add(Dimension(x1=0, y1=0, x2=100, y2=0, offset=10))
    render.apply_handle(d, "offset", (50, -80))
    assert d.offset == pytest.approx(80)


def test_dimension_text_auto_and_custom():
    doc = Document()
    d = Dimension(x1=0, y1=0, x2=350, y2=0)
    assert render.dim_geo(d, doc).text == "3,50 m"
    doc.unit = "cm"
    assert render.dim_geo(d, doc).text == "350 cm"
    d.text = "3,5 m (aprox.)"
    assert render.dim_geo(d, doc).text == "3,5 m (aprox.)"


def test_bounds_include_labels():
    doc = Document()
    assert render.document_bounds(doc) is None
    b = doc.add(Beam(x1=0, y1=0, x2=400, y2=0, label="VIGA 1"))
    r = render.element_bounds(b, doc)
    assert r.top() < -b.width / 2  # o nome fica acima da viga


def test_snap_sources_skip_excluded():
    doc = Document()
    b = doc.add(Beam(x1=0, y1=0, x2=100, y2=0))
    pts, segs = render.snap_sources(doc)
    assert (100, 0) in pts and len(segs) == 1
    pts, segs = render.snap_sources(doc, exclude={b.id})
    assert pts == [] and segs == []


def test_paint_every_kind_without_errors():
    from PySide6.QtGui import QColor, QImage, QPainter
    doc = samples.mezzanine()
    doc.add(Line(x1=0, y1=700, x2=300, y2=700, dashed=True, show_length=True))
    doc.add(Rect(x=400, y=700, w=200, h=100, fill=True, dashed=True, show_dims=True, color="#2f6fdb"))
    doc.add(Text(x=800, y=750, text="duas\nlinhas", rot=90, bold=True))
    img = QImage(400, 300, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.scale(0.3, 0.3)
    render.paint_document(p, doc, render.print_style(min_pen=0.5))
    p.end()
    assert img.pixelColor(10, 10).name() == "#ffffff"


# ------------------------------------------------------------------------------------- impressão
def test_page_options_validation():
    o = PageOptions.from_json(json.dumps({"paper": "A0", "orientation": "lado", "scale": 33, "header": 0}))
    assert (o.paper, o.orientation, o.scale, o.header, o.mono) == ("A4", "auto", 0, False, False)
    o = PageOptions.from_json("não é json")
    assert o == PageOptions()
    o = PageOptions("Oficio", "portrait", 150, True, True)
    assert PageOptions.from_json(o.to_json()) == o


def test_orientation_follows_drawing_shape():
    wide = samples.mezzanine()
    assert printing.landscape(PageOptions(), wide)
    assert printing.page_mm(PageOptions(), wide) == (297.0, 210.0)
    tall = Document()
    tall.add(Beam(x1=0, y1=0, x2=0, y2=1000))
    assert not printing.landscape(PageOptions(), tall)
    assert printing.page_mm(PageOptions(orientation="landscape"), tall) == (297.0, 210.0)


def test_fit_to_page_and_fixed_scale():
    doc = samples.mezzanine()
    fit = printing.compute_layout(doc, PageOptions())
    assert fit.fits and fit.approx and 30 < fit.denom < 80
    big = printing.compute_layout(doc, PageOptions(scale=20))
    assert not big.fits and big.k == pytest.approx(0.5)
    ok = printing.compute_layout(doc, PageOptions(scale=100))
    assert ok.fits and not ok.approx and ok.denom == 100
    assert printing.best_scale(doc, PageOptions()) == 50
    assert printing.best_scale(doc, PageOptions(paper="A3")) == 50
    assert printing.compute_layout(Document(), PageOptions()).bounds is None


def test_scale_text():
    doc = samples.mezzanine()
    assert printing.scale_text(printing.compute_layout(doc, PageOptions(scale=50)), "m") == \
        "Escala 1:50 · Medidas em metros"
    assert printing.scale_text(printing.compute_layout(doc, PageOptions()), "cm").startswith("Escala aproximada 1:")


def test_custom_paper_size():
    size = printing.page_size("Oficio")
    r = size.rect(size.Unit.Millimeter)
    assert (round(r.width()), round(r.height())) == (216, 330)
    assert printing.page_size("A2").id() == printing.PAPER_IDS["A2"]


def test_pdf_png_and_thumbnail(tmp_path):
    doc = samples.mezzanine()
    pdf = tmp_path / "planta.pdf"
    assert printing.save_pdf(doc, PageOptions(scale=50), str(pdf))
    assert pdf.read_bytes()[:5] == b"%PDF-" and pdf.stat().st_size > 2000
    png = tmp_path / "planta.png"
    assert printing.save_png(doc, PageOptions(paper="A4"), str(png), dpi=72)
    from PySide6.QtGui import QImage
    img = QImage(str(png))
    assert (img.width(), img.height()) == (842, 595)
    thumb = printing.thumbnail_png(doc)
    assert thumb[:8] == b"\x89PNG\r\n\x1a\n"
    assert printing.thumbnail(Document()).pixelColor(5, 5).name() == "#ffffff"
