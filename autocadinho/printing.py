"""Folha impressa: título, data, desenho em escala e rodapé. Também gera PDF, PNG e miniaturas.

A folha é montada em milímetros por `render_page()`, que serve à impressora, ao PDF, à imagem PNG
e à prévia da janela de impressão: o que aparece na prévia é o que sai no papel. O desenho em si é
pintado por `render.paint_document` com papel branco e tinta preta.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from PySide6.QtCore import QBuffer, QByteArray, QDate, QIODevice, QLocale, QMarginsF, QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from . import APP_NAME, render
from .i18n import N_, _
from .model import Document

PAPERS = {"A4": QPageSize.PageSizeId.A4, "A3": QPageSize.PageSizeId.A3, "Letter": QPageSize.PageSizeId.Letter}
PAPER_MM = {"A4": (210.0, 297.0), "A3": (297.0, 420.0), "Letter": (215.9, 279.4)}
PAPER_LABELS = {"A4": "A4", "A3": "A3", "Letter": N_("Carta")}
ORIENTATIONS = {"auto": N_("Automática"), "landscape": N_("Deitada"), "portrait": N_("Em pé")}
SCALES = (0, 20, 25, 50, 75, 100, 200)

MARGIN = 10.0  # mm
HEADER_H = 15.0
FOOTER_H = 7.0


@dataclass
class PageOptions:
    paper: str = "A4"
    orientation: str = "auto"  # auto | landscape | portrait
    scale: int = 0  # 0 = ajustar à folha; N = escala 1:N
    header: bool = True
    mono: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str | None) -> "PageOptions":
        opts = cls()
        try:
            data = json.loads(text or "{}")
        except ValueError:
            return opts
        if isinstance(data, dict):
            if data.get("paper") in PAPERS:
                opts.paper = data["paper"]
            if data.get("orientation") in ORIENTATIONS:
                opts.orientation = data["orientation"]
            if data.get("scale") in SCALES:
                opts.scale = int(data["scale"])
            opts.header = bool(data.get("header", True))
            opts.mono = bool(data.get("mono", False))
        return opts


@dataclass
class Layout:
    page_w: float  # mm
    page_h: float
    area: QRectF  # onde o desenho cabe (mm)
    bounds: QRectF | None  # limites do desenho (cm)
    k: float  # mm de papel por cm do desenho
    denom: int  # escala 1:denom
    fits: bool
    approx: bool  # escala calculada para caber (não é uma escala "redonda")


def landscape(opts: PageOptions, doc: Document) -> bool:
    if opts.orientation == "landscape":
        return True
    if opts.orientation == "portrait":
        return False
    b = render.document_bounds(doc)
    return b is None or b.width() >= b.height()


def page_mm(opts: PageOptions, doc: Document) -> tuple[float, float]:
    w, h = PAPER_MM.get(opts.paper, PAPER_MM["A4"])
    return (h, w) if landscape(opts, doc) else (w, h)


def page_layout(opts: PageOptions, doc: Document) -> QPageLayout:
    orient = QPageLayout.Orientation.Landscape if landscape(opts, doc) else QPageLayout.Orientation.Portrait
    return QPageLayout(QPageSize(PAPERS.get(opts.paper, PAPERS["A4"])), orient, QMarginsF(0, 0, 0, 0))


def compute_layout(doc: Document, opts: PageOptions, page: tuple[float, float] | None = None) -> Layout:
    pw, ph = page or page_mm(opts, doc)
    top = MARGIN + (HEADER_H if opts.header else 0.0)
    bottom = MARGIN + FOOTER_H
    area = QRectF(MARGIN, top, pw - 2 * MARGIN, ph - top - bottom)
    b = render.document_bounds(doc)
    if b is None:
        return Layout(pw, ph, area, None, 1.0, opts.scale or 0, True, False)
    bw, bh = max(b.width(), 1.0), max(b.height(), 1.0)
    if opts.scale:
        k = 10.0 / opts.scale
        fits = bw * k <= area.width() + 1e-6 and bh * k <= area.height() + 1e-6
        return Layout(pw, ph, area, b, k, opts.scale, fits, False)
    k = min(area.width() / bw, area.height() / bh)
    return Layout(pw, ph, area, b, k, max(1, round(10.0 / k)), True, True)


def best_scale(doc: Document, opts: PageOptions) -> int:
    """Maior escala "redonda" (1:20, 1:25, 1:50...) em que o desenho cabe na folha; 0 se nenhuma."""
    for s in SCALES[1:]:
        o = PageOptions(opts.paper, opts.orientation, s, opts.header, opts.mono)
        if compute_layout(doc, o).fits:
            return s
    return 0


def scale_text(lay: Layout, unit: str) -> str:
    units = _("Medidas em metros") if unit == "m" else _("Medidas em centímetros")
    if not lay.denom:
        return units
    if lay.approx:
        return _("Escala aproximada 1:{n}").format(n=lay.denom) + " · " + units
    return _("Escala 1:{n}").format(n=lay.denom) + " · " + units


def _text(p: QPainter, x: float, y: float, text: str, size: float, color: QColor, bold: bool = False,
          align: str = "left") -> None:
    """Escreve uma linha com a base em y (mm), alinhada à esquerda ou à direita de x."""
    w, _h = render.text_extent(text, size, bold)
    k = size / render.FONT_PX
    fm = render.text_metrics(bold)
    p.save()
    p.translate(x - (w if align == "right" else 0.0), y)
    p.scale(k, k)
    p.setFont(render.text_font(bold))
    p.setPen(QPen(color))
    p.drawText(QPointF(0, -fm.descent()), text)
    p.restore()


def render_page(p: QPainter, doc: Document, opts: PageOptions, target: QRectF,
                page: tuple[float, float] | None = None, when: QDate | None = None) -> Layout:
    """Pinta a folha inteira dentro de `target` (coordenadas do QPainter)."""
    lay = compute_layout(doc, opts, page)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.translate(target.topLeft())
    f = target.width() / lay.page_w
    p.scale(f, f)
    p.fillRect(QRectF(0, 0, lay.page_w, lay.page_h), QColor("#ffffff"))
    ink = QColor("#111111")
    grey = QColor("#6b6f76")
    rule = QPen(QColor("#b9bdc4"), 0.25)
    if opts.header:
        title = doc.title.strip() or _("Desenho sem título")
        _text(p, MARGIN, MARGIN + 7.0, title, 6.0, ink, bold=True)
        date = QLocale().toString(when or QDate.currentDate(), QLocale.FormatType.ShortFormat)
        _text(p, lay.page_w - MARGIN, MARGIN + 7.0, date, 3.6, grey, align="right")
        p.setPen(rule)
        p.drawLine(QPointF(MARGIN, MARGIN + HEADER_H - 4.0), QPointF(lay.page_w - MARGIN, MARGIN + HEADER_H - 4.0))
    fy = lay.page_h - MARGIN
    p.setPen(rule)
    p.drawLine(QPointF(MARGIN, fy - FOOTER_H + 2.0), QPointF(lay.page_w - MARGIN, fy - FOOTER_H + 2.0))
    _text(p, MARGIN, fy, scale_text(lay, doc.unit), 3.0, grey)
    _text(p, lay.page_w - MARGIN, fy, APP_NAME, 3.0, grey, align="right")
    if lay.bounds is not None:
        p.save()
        p.setClipRect(lay.area)
        c = lay.area.center()
        p.translate(c)
        p.scale(lay.k, lay.k)
        bc = lay.bounds.center()
        p.translate(-bc.x(), -bc.y())
        render.paint_document(p, doc, render.print_style(min_pen=0.12 / lay.k, mono=opts.mono))
        p.restore()
    p.restore()
    return lay


def render_image(doc: Document, opts: PageOptions, dpi: int = 200) -> QImage:
    pw, ph = page_mm(opts, doc)
    w, h = round(pw / 25.4 * dpi), round(ph / 25.4 * dpi)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#ffffff"))
    dpm = round(dpi / 0.0254)
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    p = QPainter(img)
    render_page(p, doc, opts, QRectF(0, 0, w, h), (pw, ph))
    p.end()
    return img


def save_png(doc: Document, opts: PageOptions, path: str, dpi: int = 200) -> bool:
    return render_image(doc, opts, dpi).save(path, "PNG")


def save_pdf(doc: Document, opts: PageOptions, path: str) -> bool:
    writer = QPdfWriter(path)
    writer.setResolution(300)
    writer.setCreator(APP_NAME)
    writer.setTitle(doc.title.strip() or _("Desenho sem título"))
    writer.setPageLayout(page_layout(opts, doc))
    p = QPainter()
    if not p.begin(writer):
        return False
    render_page(p, doc, opts, QRectF(0, 0, writer.width(), writer.height()), page_mm(opts, doc))
    return p.end()


def print_doc(printer, doc: Document, opts: PageOptions) -> bool:
    """Imprime numa QPrinter já configurada (com setFullPage(True))."""
    full = printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
    p = QPainter()
    if not p.begin(printer):
        return False
    paper = printer.paperRect(printer.Unit.DevicePixel)
    render_page(p, doc, opts, QRectF(0, 0, paper.width(), paper.height()), (full.width(), full.height()))
    return p.end()


def thumbnail(doc: Document, w: int = 480, h: int = 320) -> QImage:
    """Miniatura do desenho (papel branco), usada na tela inicial."""
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("#ffffff"))
    b = render.document_bounds(doc)
    if b is None:
        return img
    m = 18
    k = min((w - 2 * m) / max(b.width(), 1.0), (h - 2 * m) / max(b.height(), 1.0))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.translate(w / 2, h / 2)
    p.scale(k, k)
    p.translate(-b.center().x(), -b.center().y())
    render.paint_document(p, doc, render.print_style(min_pen=1.0 / k))
    p.end()
    return img


def thumbnail_png(doc: Document) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    thumbnail(doc).save(buf, "PNG")
    buf.close()
    return bytes(data.data())

