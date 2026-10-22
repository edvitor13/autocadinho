"""Desenho do documento com QPainter e as contas que dependem do tamanho dos textos.

O MESMO código pinta a tela, a impressão, o PDF, a imagem PNG e as miniaturas: quem chama só
escolhe o estilo (cor da tinta, do papel, traço mínimo) e a transformação do QPainter. As
coordenadas do QPainter chegam em centímetros do desenho.

Também ficam aqui o teste de clique (`hit`), a seleção por área, as alças de edição e as fontes de
encaixe, porque precisam saber onde os textos e os nomes ficam.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPen

from . import geometry as geo
from . import i18n
from .geometry import Point, Seg
from .model import Beam, Dimension, Document, Element, Labeled, Line, Pillar, Rect, Segment, Text

FONT_PX = 100.0  # os textos são montados numa fonte de 100 px e escalados para o tamanho em cm


@dataclass
class Style:
    ink: QColor  # cor da "tinta" (elementos sem cor própria)
    paper: QColor
    min_pen: float = 0.0  # traço mínimo (cm): na tela, 1 px; na impressão, ~0,1 mm
    mono: bool = False  # tudo na cor da tinta (impressão em preto e branco)


def print_style(min_pen: float = 0.0, mono: bool = False) -> Style:
    return Style(QColor("#111111"), QColor("#ffffff"), min_pen, mono)


# ------------------------------------------------------------------------------------- textos
@lru_cache(maxsize=1)
def font_family() -> str:
    fams = set(QFontDatabase.families())
    for f in ("Segoe UI", "Arial", "Helvetica", "DejaVu Sans", "Liberation Sans"):
        if f in fams:
            return f
    return QFont().defaultFamily()


@lru_cache(maxsize=2)
def text_font(bold: bool) -> QFont:
    f = QFont(font_family())
    f.setPixelSize(int(FONT_PX))
    f.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    f.setKerning(True)
    # Sem ClearType: o texto do desenho é girado e escalado, e o subpixel deixaria franjas coloridas.
    f.setStyleStrategy(QFont.StyleStrategy.NoSubpixelAntialias)
    return f


@lru_cache(maxsize=2)
def text_metrics(bold: bool) -> QFontMetricsF:
    return QFontMetricsF(text_font(bold))


def text_extent(text: str, size: float, bold: bool = False) -> tuple[float, float]:
    """Largura e altura (cm) de um texto deitado com letras de `size` cm."""
    fm = text_metrics(bold)
    lines = text.split("\n") if text else [""]
    w = max(fm.horizontalAdvance(line) for line in lines)
    h = fm.height() * len(lines)
    k = size / FONT_PX
    return w * k, h * k


def draw_text(p: QPainter, center: Point, text: str, size: float, color: QColor, angle: float = 0.0,
              bold: bool = False) -> None:
    """Escreve `text` centralizado em `center`, girado `angle` graus, com letras de `size` cm."""
    if not text:
        return
    p.save()
    p.translate(center[0], center[1])
    if angle:
        p.rotate(angle)
    k = size / FONT_PX
    p.scale(k, k)
    font = text_font(bold)
    fm = text_metrics(bold)
    p.setFont(font)
    p.setPen(QPen(color))
    lines = text.split("\n")
    lh = fm.height()
    y = -lh * len(lines) / 2
    for line in lines:
        w = fm.horizontalAdvance(line)
        p.drawText(QPointF(-w / 2, y + fm.ascent()), line)
        y += lh
    p.restore()


@dataclass
class Box:
    """Caixa de texto: centro, largura e altura (deitada) e ângulo."""

    cx: float
    cy: float
    w: float
    h: float
    angle: float = 0.0

    def contains(self, pt: Point, tol: float = 0.0) -> bool:
        r = math.radians(-self.angle)
        dx, dy = pt[0] - self.cx, pt[1] - self.cy
        lx = dx * math.cos(r) - dy * math.sin(r)
        ly = dx * math.sin(r) + dy * math.cos(r)
        return abs(lx) <= self.w / 2 + tol and abs(ly) <= self.h / 2 + tol

    def rect(self) -> QRectF:
        r = math.radians(self.angle)
        c, s = abs(math.cos(r)), abs(math.sin(r))
        bw = self.w * c + self.h * s
        bh = self.w * s + self.h * c
        return QRectF(self.cx - bw / 2, self.cy - bh / 2, bw, bh)


def fmt_len(cm: float, doc: Document) -> str:
    return geo.format_length(cm, doc.unit, i18n.decimal_sep())


def annotation_size(doc: Document) -> float:
    """Tamanho das letras das medidas (um pouco menor que os nomes)."""
    return doc.label_size * 0.85


def thin_width(doc: Document) -> float:
    """Traço fino das medidas (cm), proporcional ao tamanho das letras."""
    return max(doc.label_size * 0.05, 0.5)


# ------------------------------------------------------------------------------------- nomes
def label_box(el: Element, doc: Document) -> Box | None:
    """Onde fica o nome do elemento (None se não tiver nome visível)."""
    if not isinstance(el, Labeled) or not el.label_visible or not el.label.strip():
        return None
    bold = isinstance(el, Beam)
    w, h = text_extent(el.label, doc.label_size, bold)
    angle = -90.0 if el.label_rot else 0.0
    bw, bh = (h, w) if el.label_rot else (w, h)
    ax, ay = el.label_anchor()
    if el.label_dx is not None and el.label_dy is not None:
        return Box(ax + el.label_dx, ay + el.label_dy, w, h, angle)
    gap = doc.label_size * 0.35
    if isinstance(el, Segment):
        nx, ny = geo.normal_up(el.p1, el.p2)
        ext = abs(nx) * bw / 2 + abs(ny) * bh / 2
        off = el.width / 2 + gap + ext
        return Box(ax + nx * off, ay + ny * off, w, h, angle)
    if isinstance(el, Pillar):
        if el.w >= el.h:  # pilar deitado: nome embaixo
            return Box(ax, ay + el.h / 2 + gap + bh / 2, w, h, angle)
        return Box(ax - el.w / 2 - gap - bw / 2, ay, w, h, angle)
    return Box(ax, ay, w, h, angle)


def materialize_label(el: Element, doc: Document) -> None:
    """Grava a posição atual do nome (automática) para poder arrastá-lo."""
    if isinstance(el, Labeled) and (el.label_dx is None or el.label_dy is None):
        box = label_box(el, doc)
        if box is not None:
            ax, ay = el.label_anchor()
            el.label_dx, el.label_dy = box.cx - ax, box.cy - ay


def length_box(el: Segment, doc: Document) -> Box | None:
    """Onde fica a medida escrita ao lado de uma viga/linha (do lado oposto ao nome)."""
    if not el.show_length or el.length() < 1e-6:
        return None
    size = annotation_size(doc)
    text = fmt_len(el.length(), doc)
    w, h = text_extent(text, size)
    nx, ny = geo.normal_up(el.p1, el.p2)
    off = el.width / 2 + size * 0.3 + h / 2
    c = geo.mid(el.p1, el.p2)
    return Box(c[0] - nx * off, c[1] - ny * off, w, h, geo.readable_angle(el.p1, el.p2))


def rect_dim_boxes(el: Rect, doc: Document) -> list[tuple[str, Box]]:
    if not el.show_dims:
        return []
    size = annotation_size(doc)
    gap = el.width / 2 + size * 0.3
    tw = fmt_len(el.w, doc)
    th = fmt_len(el.h, doc)
    w1, h1 = text_extent(tw, size)
    w2, h2 = text_extent(th, size)
    return [
        (tw, Box(el.x + el.w / 2, el.y - gap - h1 / 2, w1, h1, 0.0)),
        (th, Box(el.x - gap - h2 / 2, el.y + el.h / 2, w2, h2, -90.0)),
    ]


# ------------------------------------------------------------------------------------- medidas
@dataclass
class DimGeo:
    a: Point  # pontos medidos
    b: Point
    a2: Point  # pontas da linha de cota
    b2: Point
    n: Point
    text: str
    box: Box
    size: float


def dim_geo(d: Dimension, doc: Document) -> DimGeo:
    a, b = d.p1, d.p2
    nx, ny = d.normal()
    a2 = (a[0] + nx * d.offset, a[1] + ny * d.offset)
    b2 = (b[0] + nx * d.offset, b[1] + ny * d.offset)
    size = annotation_size(doc)
    text = d.text.strip() or fmt_len(d.length(), doc)
    ang = geo.readable_angle(a2, b2)
    w, h = text_extent(text, size)
    ux, uy = geo.text_up(ang)
    m = geo.mid(a2, b2)
    off = h / 2 + size * 0.12
    return DimGeo(a, b, a2, b2, (nx, ny), text, Box(m[0] + ux * off, m[1] + uy * off, w, h, ang), size)


# ------------------------------------------------------------------------------------- pintura
def color_of(el: Element, style: Style) -> QColor:
    if style.mono or not el.color:
        return QColor(style.ink)
    c = QColor(el.color)
    return c if c.isValid() else QColor(style.ink)


def _pen(color: QColor, width: float, style: Style, cap=Qt.PenCapStyle.FlatCap,
         join=Qt.PenJoinStyle.MiterJoin) -> QPen:
    pen = QPen(color, max(width, style.min_pen))
    pen.setCapStyle(cap)
    pen.setJoinStyle(join)
    return pen


def paint_document(p: QPainter, doc: Document, style: Style, skip: frozenset[str] | set[str] = frozenset()) -> None:
    for el in doc.elements:
        if el.id not in skip:
            paint_element(p, el, doc, style)


def paint_element(p: QPainter, el: Element, doc: Document, style: Style, color: QColor | None = None) -> None:
    c = QColor(color) if color is not None else color_of(el, style)
    p.save()
    if isinstance(el, Segment):
        _paint_segment(p, el, doc, style, c)
    elif isinstance(el, Pillar):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c))
        p.drawRect(QRectF(el.x - el.w / 2, el.y - el.h / 2, el.w, el.h))
    elif isinstance(el, Rect):
        pen = _pen(c, el.width, style, Qt.PenCapStyle.SquareCap)
        if el.dashed:
            pen.setDashPattern([4.0, 2.5])
        p.setPen(pen)
        if el.fill:
            fill = QColor(c)
            fill.setAlphaF(0.16)
            p.setBrush(QBrush(fill))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(el.x, el.y, el.w, el.h))
        for text, box in rect_dim_boxes(el, doc):
            draw_text(p, (box.cx, box.cy), text, annotation_size(doc), c, box.angle)
    elif isinstance(el, Text):
        draw_text(p, (el.x, el.y), el.text, el.size, c, -90.0 if el.rot else 0.0, el.bold)
    elif isinstance(el, Dimension):
        _paint_dimension(p, el, doc, style, c)
    box = label_box(el, doc)
    if box is not None:
        draw_text(p, (box.cx, box.cy), el.label, doc.label_size, c, box.angle, isinstance(el, Beam))
    p.restore()


def _paint_segment(p: QPainter, el: Segment, doc: Document, style: Style, c: QColor) -> None:
    if el.length() < 1e-6:
        return
    if isinstance(el, Beam):
        pen = _pen(c, el.width, style, Qt.PenCapStyle.SquareCap)
    else:
        pen = _pen(c, el.width, style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        if isinstance(el, Line) and el.dashed:
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setDashPattern([4.0, 2.5])
    p.setPen(pen)
    p.drawLine(QPointF(*el.p1), QPointF(*el.p2))
    box = length_box(el, doc)
    if box is not None:
        draw_text(p, (box.cx, box.cy), fmt_len(el.length(), doc), annotation_size(doc), c, box.angle)


def _paint_dimension(p: QPainter, d: Dimension, doc: Document, style: Style, c: QColor) -> None:
    g = dim_geo(d, doc)
    if d.length() < 1e-6:
        return
    thin = _pen(c, thin_width(doc), style, Qt.PenCapStyle.FlatCap)
    p.setPen(thin)
    ux, uy = geo.unit(g.a, g.b)
    nx, ny = g.n
    sgn = 1.0 if d.offset >= 0 else -1.0
    gap = g.size * 0.25
    ext = g.size * 0.3
    if abs(d.offset) > gap:  # linhas de chamada
        for base, end in ((g.a, g.a2), (g.b, g.b2)):
            p.drawLine(QPointF(base[0] + nx * sgn * gap, base[1] + ny * sgn * gap),
                       QPointF(end[0] + nx * sgn * ext, end[1] + ny * sgn * ext))
    over = g.size * 0.25
    p.drawLine(QPointF(g.a2[0] - ux * over, g.a2[1] - uy * over), QPointF(g.b2[0] + ux * over, g.b2[1] + uy * over))
    # tracinhos a 45°
    t = g.size * 0.28
    tx, ty = (ux + nx) / math.sqrt(2) * t, (uy + ny) / math.sqrt(2) * t
    p.setPen(_pen(c, thin_width(doc) * 2.2, style, Qt.PenCapStyle.FlatCap))
    for q in (g.a2, g.b2):
        p.drawLine(QPointF(q[0] - tx, q[1] - ty), QPointF(q[0] + tx, q[1] + ty))
    draw_text(p, (g.box.cx, g.box.cy), g.text, g.size, c, g.box.angle)


# ------------------------------------------------------------------------------------- limites
def element_bounds(el: Element, doc: Document) -> QRectF:
    if isinstance(el, Segment):
        hw = el.width / 2
        r = QRectF(QPointF(min(el.x1, el.x2) - hw, min(el.y1, el.y2) - hw),
                   QPointF(max(el.x1, el.x2) + hw, max(el.y1, el.y2) + hw))
        box = length_box(el, doc)
        if box is not None:
            r = r.united(box.rect())
    elif isinstance(el, Pillar):
        r = QRectF(el.x - el.w / 2, el.y - el.h / 2, el.w, el.h)
    elif isinstance(el, Rect):
        hw = el.width / 2
        r = QRectF(el.x - hw, el.y - hw, el.w + 2 * hw, el.h + 2 * hw)
        for _t, box in rect_dim_boxes(el, doc):
            r = r.united(box.rect())
    elif isinstance(el, Text):
        w, h = text_extent(el.text or " ", el.size, el.bold)
        r = Box(el.x, el.y, w, h, -90.0 if el.rot else 0.0).rect()
    elif isinstance(el, Dimension):
        g = dim_geo(el, doc)
        xs = [g.a[0], g.b[0], g.a2[0], g.b2[0]]
        ys = [g.a[1], g.b[1], g.a2[1], g.b2[1]]
        r = QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys))).united(g.box.rect())
        r = r.adjusted(-g.size * 0.3, -g.size * 0.3, g.size * 0.3, g.size * 0.3)
    else:
        c = el.center()
        r = QRectF(c[0], c[1], 0, 0)
    box = label_box(el, doc)
    if box is not None:
        r = r.united(box.rect())
    return r


def document_bounds(doc: Document, ids=None) -> QRectF | None:
    r: QRectF | None = None
    for el in doc.elements:
        if ids is not None and el.id not in ids:
            continue
        b = element_bounds(el, doc)
        r = b if r is None else r.united(b)
    return r


# ------------------------------------------------------------------------------------- clique
def hit_body(el: Element, doc: Document, pt: Point, tol: float) -> bool:
    if isinstance(el, Segment):
        if geo.dist_to_segment(pt, el.p1, el.p2) <= el.width / 2 + tol:
            return True
        box = length_box(el, doc)
        return box is not None and box.contains(pt, tol)
    if isinstance(el, Pillar):
        return abs(pt[0] - el.x) <= el.w / 2 + tol and abs(pt[1] - el.y) <= el.h / 2 + tol
    if isinstance(el, Rect):
        if el.fill and el.x - tol <= pt[0] <= el.x + el.w + tol and el.y - tol <= pt[1] <= el.y + el.h + tol:
            return True
        if any(geo.dist_to_segment(pt, a, b) <= el.width / 2 + tol for a, b in el.snap_segments()):
            return True
        return any(box.contains(pt, tol) for _t, box in rect_dim_boxes(el, doc))
    if isinstance(el, Text):
        w, h = text_extent(el.text or " ", el.size, el.bold)
        return Box(el.x, el.y, w, h, -90.0 if el.rot else 0.0).contains(pt, tol)
    if isinstance(el, Dimension):
        g = dim_geo(el, doc)
        if geo.dist_to_segment(pt, g.a2, g.b2) <= tol or g.box.contains(pt, tol):
            return True
        return any(geo.dist_to_segment(pt, s, e) <= tol for s, e in ((g.a, g.a2), (g.b, g.b2)))
    return False


def hit(doc: Document, pt: Point, tol: float) -> tuple[str, str] | None:
    """Elemento mais à frente sob o ponto: (id, "label" ou "body")."""
    for el in reversed(doc.elements):
        box = label_box(el, doc)
        if box is not None and box.contains(pt, tol):
            return el.id, "label"
        if hit_body(el, doc, pt, tol):
            return el.id, "body"
    return None


def touching(doc: Document, rect: QRectF) -> list[str]:
    """Elementos que encostam no retângulo (seleção por área)."""
    r = rect.normalized()
    box = (r.left(), r.top(), r.right(), r.bottom())
    out = []
    for el in doc.elements:
        if isinstance(el, Segment):
            if geo.segment_touches_rect(el.p1, el.p2, box):
                out.append(el.id)
                continue
        elif isinstance(el, Rect) and not el.fill:
            if any(geo.segment_touches_rect(a, b, box) for a, b in el.snap_segments()):
                out.append(el.id)
                continue
        elif element_bounds(el, doc).intersects(r):
            out.append(el.id)
            continue
        lb = label_box(el, doc)
        if lb is not None and lb.rect().intersects(r):
            out.append(el.id)
    return out


# ------------------------------------------------------------------------------------- alças
def handles(el: Element, doc: Document) -> list[tuple[str, Point]]:
    if isinstance(el, Segment):
        return [("p1", el.p1), ("p2", el.p2)]
    if isinstance(el, Dimension):
        g = dim_geo(el, doc)
        return [("p1", el.p1), ("p2", el.p2), ("offset", geo.mid(g.a2, g.b2))]
    if isinstance(el, Rect):
        x0, y0, x1, y1 = el.x, el.y, el.x + el.w, el.y + el.h
        return [("tl", (x0, y0)), ("tr", (x1, y0)), ("br", (x1, y1)), ("bl", (x0, y1))]
    return []


def handle_anchor(el: Element, name: str) -> Point | None:
    """Ponto que fica parado enquanto a alça `name` é arrastada (para as retas a 90°)."""
    if isinstance(el, (Segment, Dimension)):
        return el.p2 if name == "p1" else el.p1 if name == "p2" else None
    if isinstance(el, Rect):
        x0, y0, x1, y1 = el.x, el.y, el.x + el.w, el.y + el.h
        opposite = {"tl": (x1, y1), "br": (x0, y0), "tr": (x0, y1), "bl": (x1, y0)}
        return opposite.get(name)
    return None


def apply_handle(el: Element, name: str, pt: Point, anchor: Point | None = None) -> None:
    """Move a alça `name` para `pt`. No retângulo, `anchor` é o canto oposto (gravado no começo do arraste)."""
    if isinstance(el, (Segment, Dimension)):
        if name == "p1":
            el.x1, el.y1 = pt
        elif name == "p2":
            el.x2, el.y2 = pt
        elif name == "offset" and isinstance(el, Dimension):
            nx, ny = el.normal()
            el.offset = (pt[0] - el.x1) * nx + (pt[1] - el.y1) * ny
    elif isinstance(el, Rect):
        anchor = anchor if anchor is not None else handle_anchor(el, name)
        if anchor is not None:
            el.x, el.y, el.w, el.h = geo.rect_norm(anchor[0], anchor[1], pt[0], pt[1])


# ------------------------------------------------------------------------------------- encaixe
def snap_sources(doc: Document, exclude=()) -> tuple[list[Point], list[Seg]]:
    exclude = set(exclude)
    points: list[Point] = []
    segments: list[Seg] = []
    for el in doc.elements:
        if el.id in exclude:
            continue
        points += el.key_points()
        segments += el.snap_segments()
    return points, segments
