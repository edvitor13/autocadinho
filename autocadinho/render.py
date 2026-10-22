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
from PySide6.QtGui import QBrush, QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen

from . import geometry as geo
from . import i18n
from .geometry import Point, Seg
from .model import (Beam, Dimension, Document, Element, Ellipse, Labeled, Line, Pillar, Polygon, Rect, Segment, Symbol,
                    Text)

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


def family_of(name: str) -> str:
    """Família para escrever: a escolhida ou, sem escolha, a padrão do app."""
    return name.strip() or font_family()


@lru_cache(maxsize=64)
def text_font(bold: bool, family: str = "", italic: bool = False) -> QFont:
    f = QFont(family_of(family))
    f.setPixelSize(int(FONT_PX))
    f.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    f.setItalic(italic)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    f.setKerning(True)
    # Sem ClearType: o texto do desenho é girado e escalado, e o subpixel deixaria franjas coloridas.
    f.setStyleStrategy(QFont.StyleStrategy.NoSubpixelAntialias)
    return f


@lru_cache(maxsize=64)
def text_metrics(bold: bool, family: str = "", italic: bool = False) -> QFontMetricsF:
    return QFontMetricsF(text_font(bold, family, italic))


def text_extent(text: str, size: float, bold: bool = False, family: str = "", italic: bool = False) -> tuple[float, float]:
    """Largura e altura (cm) de um texto deitado com letras de `size` cm."""
    fm = text_metrics(bold, family, italic)
    lines = text.split("\n") if text else [""]
    w = max(fm.horizontalAdvance(line) for line in lines)
    h = fm.height() * len(lines)
    k = size / FONT_PX
    return w * k, h * k


def draw_text(p: QPainter, center: Point, text: str, size: float, color: QColor, angle: float = 0.0,
              bold: bool = False, family: str = "", italic: bool = False) -> None:
    """Escreve `text` centralizado em `center`, girado `angle` graus, com letras de `size` cm."""
    if not text:
        return
    p.save()
    p.translate(center[0], center[1])
    if angle:
        p.rotate(angle)
    k = size / FONT_PX
    p.scale(k, k)
    font = text_font(bold, family, italic)
    fm = text_metrics(bold, family, italic)
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
    w, h = text_extent(el.label, doc.label_size, bold, doc.font)
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
    if isinstance(el, Symbol):  # embaixo do símbolo
        return Box(ax, symbol_rect(el).bottom() + gap + bh / 2, w, h, angle)
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
    w, h = text_extent(text, size, family=doc.font)
    nx, ny = geo.normal_up(el.p1, el.p2)
    off = el.width / 2 + size * 0.3 + h / 2
    c = geo.mid(el.p1, el.p2)
    return Box(c[0] - nx * off, c[1] - ny * off, w, h, geo.readable_angle(el.p1, el.p2))


def rect_dim_boxes(el: Rect | Ellipse, doc: Document) -> list[tuple[str, Box]]:
    """Medidas escritas em volta do retângulo ou do círculo (largura em cima, altura à esquerda; Ø no círculo)."""
    if not el.show_dims:
        return []
    size = annotation_size(doc)
    gap = el.width / 2 + size * 0.3
    tw = fmt_len(el.w, doc)
    if isinstance(el, Ellipse) and el.is_circle():
        tw = "Ø " + tw
    w1, h1 = text_extent(tw, size, family=doc.font)
    out = [(tw, Box(el.x + el.w / 2, el.y - gap - h1 / 2, w1, h1, 0.0))]
    if not (isinstance(el, Ellipse) and el.is_circle()):
        th = fmt_len(el.h, doc)
        w2, h2 = text_extent(th, size, family=doc.font)
        out.append((th, Box(el.x - gap - h2 / 2, el.y + el.h / 2, w2, h2, -90.0)))
    return out


def area_box(el: Element, doc: Document) -> tuple[str, Box] | None:
    """Área escrita no meio da forma ("12,50 m²"), quando pedida."""
    if not isinstance(el, (Rect, Ellipse, Polygon)) or not el.show_area:
        return None
    if isinstance(el, Rect):
        area, c = el.w * el.h, el.center()
    elif isinstance(el, Ellipse):
        area, c = el.area(), el.center()
    else:
        area = el.area()
        c = geo.polygon_centroid(el.pts()) if area > 0 else el.center()
    if area <= 0:
        return None
    size = annotation_size(doc)
    text = geo.format_area(area, i18n.decimal_sep())
    w, h = text_extent(text, size, family=doc.font)
    return text, Box(c[0], c[1], w, h, 0.0)


def poly_length_boxes(el: Polygon, doc: Document) -> list[tuple[str, Box]]:
    """Medida de cada lado do polígono, escrita do lado de fora."""
    if not el.show_lengths:
        return []
    size = annotation_size(doc)
    signed = geo.polygon_area(el.pts()) if el.closed and len(el.points) > 2 else 0.0
    out = []
    for a, b in el.sides():
        length = geo.dist(a, b)
        if length < 1e-6:
            continue
        text = fmt_len(length, doc)
        w, h = text_extent(text, size, family=doc.font)
        ux, uy = geo.unit(a, b)
        if signed > 0:
            nx, ny = uy, -ux
        elif signed < 0:
            nx, ny = -uy, ux
        else:
            nx, ny = geo.normal_up(a, b)
        off = el.width / 2 + size * 0.3 + h / 2
        c = geo.mid(a, b)
        out.append((text, Box(c[0] + nx * off, c[1] + ny * off, w, h, geo.readable_angle(a, b))))
    return out


def symbol_rect(el: Symbol) -> QRectF:
    """Retângulo (alinhado à folha) que envolve o símbolo."""
    pts = el.corners()
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys)))


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
    w, h = text_extent(text, size, family=doc.font)
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


def is_opening(el: Element) -> bool:
    """Porta ou janela que abre um vão na parede (pintada por cima de tudo para cobrir a parede)."""
    return isinstance(el, Symbol) and el.in_wall() and el.wall > 0


def paint_order(doc: Document) -> list[Element]:
    """Ordem de pintura: a do desenho, com as portas e janelas que abrem a parede por último."""
    return [el for el in doc.elements if not is_opening(el)] + [el for el in doc.elements if is_opening(el)]


def paint_document(p: QPainter, doc: Document, style: Style, skip: frozenset[str] | set[str] = frozenset()) -> None:
    for el in paint_order(doc):
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
    elif isinstance(el, (Rect, Ellipse, Polygon)):
        _outline(p, el, style, c)
        if isinstance(el, Rect):
            p.drawRect(QRectF(el.x, el.y, el.w, el.h))
        elif isinstance(el, Ellipse):
            p.drawEllipse(QRectF(el.x, el.y, el.w, el.h))
        elif len(el.points) > 1:
            p.drawPath(_poly_path(el))
        notes = poly_length_boxes(el, doc) if isinstance(el, Polygon) else rect_dim_boxes(el, doc)
        area = area_box(el, doc)
        for text, box in notes + ([area] if area else []):
            draw_text(p, (box.cx, box.cy), text, annotation_size(doc), c, box.angle, family=doc.font)
    elif isinstance(el, Symbol):
        _paint_symbol(p, el, doc, style, c)
    elif isinstance(el, Text):
        draw_text(p, (el.x, el.y), el.text, el.size, c, -90.0 if el.rot else 0.0, el.bold, el.font or doc.font,
                  el.italic)
    elif isinstance(el, Dimension):
        _paint_dimension(p, el, doc, style, c)
    box = label_box(el, doc)
    if box is not None:
        draw_text(p, (box.cx, box.cy), el.label, doc.label_size, c, box.angle, isinstance(el, Beam), doc.font)
    p.restore()


def _outline(p: QPainter, el: Rect | Ellipse | Polygon, style: Style, c: QColor) -> None:
    """Caneta e preenchimento das formas (contorno cheio ou tracejado; preenchimento claro)."""
    closed = not isinstance(el, Polygon) or el.closed
    pen = _pen(c, el.width, style, Qt.PenCapStyle.SquareCap if closed else Qt.PenCapStyle.RoundCap,
               Qt.PenJoinStyle.MiterJoin if closed else Qt.PenJoinStyle.RoundJoin)
    if el.dashed:
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen.setDashPattern([4.0, 2.5])
    p.setPen(pen)
    if el.fill and closed:
        fill = QColor(c)
        fill.setAlphaF(0.16)
        p.setBrush(QBrush(fill))
    else:
        p.setBrush(Qt.BrushStyle.NoBrush)


def _poly_path(el: Polygon) -> QPainterPath:
    pts = el.pts()
    path = QPainterPath(QPointF(*pts[0]))
    for q in pts[1:]:
        path.lineTo(QPointF(*q))
    if el.closed and len(pts) > 2:
        path.closeSubpath()
    return path


def _arrowhead(p: QPainter, tip: Point, u: Point, length: float, c: QColor) -> None:
    """Ponta de seta cheia em `tip`, apontando na direção unitária `u`."""
    bx, by = tip[0] - u[0] * length, tip[1] - u[1] * length
    nx, ny = -u[1] * length * 0.36, u[0] * length * 0.36
    path = QPainterPath(QPointF(*tip))
    path.lineTo(bx + nx, by + ny)
    path.lineTo(bx - nx, by - ny)
    path.closeSubpath()
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(c))
    p.drawPath(path)
    p.restore()


def arrow_length(el: Line, doc: Document) -> float:
    return max(el.width * 5, doc.label_size * 0.7)


def _paint_symbol(p: QPainter, el: Symbol, doc: Document, style: Style, c: QColor) -> None:  # noqa: C901
    """Desenha o símbolo no sistema dele (x ao longo da parede ou do comprimento, y para dentro)."""
    p.save()
    p.translate(el.x, el.y)
    p.rotate(el.angle)
    p.scale(-1.0 if el.flip_x else 1.0, -1.0 if el.flip_y else 1.0)
    lw = thin_width(doc)
    thin = _pen(c, lw, style, Qt.PenCapStyle.FlatCap)
    w, h = el.w, el.h
    hw, hh = w / 2, h / 2
    if el.in_wall():
        if el.wall > 0:  # cobre a parede no vão com a cor do papel
            m = max(style.min_pen, 0.4) * 1.5
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(style.paper))
            p.drawRect(QRectF(-hw, -el.wall / 2 - m, w, el.wall + 2 * m))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(thin)
        t = el.thickness() / 2 if el.shape in ("sliding", "window") else el.wall / 2
        if t > 0:  # batentes
            for x in (-hw, hw):
                p.drawLine(QPointF(x, -t), QPointF(x, t))
        leaf = _pen(c, max(lw * 1.8, w * 0.025), style, Qt.PenCapStyle.FlatCap)
        if el.shape == "door":
            p.setPen(leaf)
            p.drawLine(QPointF(-hw, 0), QPointF(-hw, w))
            p.setPen(thin)
            p.drawArc(QRectF(-hw - w, -w, 2 * w, 2 * w), 270 * 16, 90 * 16)
        elif el.shape == "door2":
            p.setPen(leaf)
            p.drawLine(QPointF(-hw, 0), QPointF(-hw, hw))
            p.drawLine(QPointF(hw, 0), QPointF(hw, hw))
            p.setPen(thin)
            p.drawArc(QRectF(-w, -hw, w, w), 270 * 16, 90 * 16)
            p.drawArc(QRectF(0, -hw, w, w), 180 * 16, 90 * 16)
        elif el.shape == "sliding":
            t2 = el.thickness()
            lt = max(t2 * 0.22, lw)
            p.drawRect(QRectF(-hw, -t2 * 0.18 - lt / 2, w * 0.56, lt))
            p.drawRect(QRectF(hw - w * 0.56, t2 * 0.18 - lt / 2, w * 0.56, lt))
        else:  # janela: faces da parede e o vidro no meio
            for y in (-t, -t * 0.15, t * 0.15, t):
                p.drawLine(QPointF(-hw, y), QPointF(hw, y))
        p.restore()
        return
    p.setPen(thin)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if el.shape == "stairs":
        p.drawRect(QRectF(-hw, -hh, w, h))
        n = el.step_count()
        step = w / n
        for i in range(1, n):
            x = -hw + step * i
            p.drawLine(QPointF(x, -hh), QPointF(x, hh))
        x0, x1 = -hw + step / 2, hw - step * 0.3
        length = min(h * 0.2, step * 1.2)
        p.drawLine(QPointF(x0, 0), QPointF(x1 - length * 0.5, 0))
        _arrowhead(p, (x1, 0), (1.0, 0.0), length, c)
        r = min(h * 0.04, step * 0.2)
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(x0, 0), r, r)
    elif el.shape == "toilet":
        tank = h * 0.26
        p.drawRoundedRect(QRectF(-hw, -hh, w, tank), w * 0.06, w * 0.06)
        bowl = h - tank
        p.drawEllipse(QRectF(-w * 0.43, -hh + tank, w * 0.86, bowl))
        p.drawEllipse(QRectF(-w * 0.29, -hh + tank + bowl * 0.14, w * 0.58, bowl * 0.72))
    elif el.shape == "sink":
        p.drawRoundedRect(QRectF(-hw, -hh, w, h), min(w, h) * 0.12, min(w, h) * 0.12)
        p.drawEllipse(QRectF(-w * 0.36, -hh + h * 0.24, w * 0.72, h * 0.64))
        r = min(w, h) * 0.045
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(0, -hh + h * 0.13), r, r)
    elif el.shape == "shower":
        p.drawRect(QRectF(-hw, -hh, w, h))
        p.drawLine(QPointF(-hw, -hh), QPointF(hw, hh))
        r = min(w, h) * 0.08
        p.setBrush(QBrush(style.paper))
        p.drawEllipse(QPointF(0, 0), r, r)
        p.drawLine(QPointF(-r * 0.6, 0), QPointF(r * 0.6, 0))
        p.drawLine(QPointF(0, -r * 0.6), QPointF(0, r * 0.6))
    elif el.shape == "north":
        r = min(w, h) / 2
        p.drawEllipse(QPointF(0, 0), r, r)
        tip, notch = QPointF(0, -r * 0.9), QPointF(0, r * 0.3)
        left, right = QPointF(-r * 0.34, r * 0.62), QPointF(r * 0.34, r * 0.62)
        p.setBrush(QBrush(c))
        half = QPainterPath(tip)
        half.lineTo(left)
        half.lineTo(notch)
        half.closeSubpath()
        p.drawPath(half)
        p.setBrush(Qt.BrushStyle.NoBrush)
        whole = QPainterPath(tip)
        for q in (right, notch, left):
            whole.lineTo(q)
        whole.closeSubpath()
        p.drawPath(whole)
        size = r * 0.5
        draw_text(p, (0, -r - size * 0.75), "N", size, c, 0.0, True, doc.font)
    else:  # símbolo de uma versão mais nova: só a caixa
        p.drawRect(QRectF(-hw, -hh, w, h))
    p.restore()


def _paint_segment(p: QPainter, el: Segment, doc: Document, style: Style, c: QColor) -> None:
    if el.length() < 1e-6:
        return
    a, b = el.p1, el.p2
    if isinstance(el, Beam):
        pen = _pen(c, el.width, style, Qt.PenCapStyle.SquareCap)
    else:
        pen = _pen(c, el.width, style, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        if isinstance(el, Line) and el.dashed:
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setDashPattern([4.0, 2.5])
        if isinstance(el, Line) and (el.arrow_start or el.arrow_end):
            length = min(arrow_length(el, doc), el.length() * 0.45)
            ux, uy = geo.unit(a, b)
            if el.arrow_end:
                _arrowhead(p, b, (ux, uy), length, c)
                b = (b[0] - ux * length * 0.8, b[1] - uy * length * 0.8)
            if el.arrow_start:
                _arrowhead(p, a, (-ux, -uy), length, c)
                a = (a[0] + ux * length * 0.8, a[1] + uy * length * 0.8)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    p.drawLine(QPointF(*a), QPointF(*b))
    box = length_box(el, doc)
    if box is not None:
        draw_text(p, (box.cx, box.cy), fmt_len(el.length(), doc), annotation_size(doc), c, box.angle, family=doc.font)


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
    draw_text(p, (g.box.cx, g.box.cy), g.text, g.size, c, g.box.angle, family=doc.font)


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
    elif isinstance(el, (Rect, Ellipse)):
        hw = el.width / 2
        r = QRectF(el.x - hw, el.y - hw, el.w + 2 * hw, el.h + 2 * hw)
        for _t, box in rect_dim_boxes(el, doc):
            r = r.united(box.rect())
    elif isinstance(el, Polygon):
        pts = el.pts() or [(0.0, 0.0)]
        hw = el.width / 2
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        r = QRectF(QPointF(min(xs) - hw, min(ys) - hw), QPointF(max(xs) + hw, max(ys) + hw))
        for _t, box in poly_length_boxes(el, doc):
            r = r.united(box.rect())
    elif isinstance(el, Symbol):
        r = symbol_rect(el)
    elif isinstance(el, Text):
        r = text_box(el, doc).rect()
    elif isinstance(el, Dimension):
        g = dim_geo(el, doc)
        xs = [g.a[0], g.b[0], g.a2[0], g.b2[0]]
        ys = [g.a[1], g.b[1], g.a2[1], g.b2[1]]
        r = QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys))).united(g.box.rect())
        r = r.adjusted(-g.size * 0.3, -g.size * 0.3, g.size * 0.3, g.size * 0.3)
    else:
        c = el.center()
        r = QRectF(c[0], c[1], 0, 0)
    for box in (label_box(el, doc), (area_box(el, doc) or ("", None))[1]):
        if box is not None:
            r = r.united(box.rect())
    return r


def text_box(el: Text, doc: Document) -> Box:
    w, h = text_extent(el.text or " ", el.size, el.bold, el.font or doc.font, el.italic)
    return Box(el.x, el.y, w, h, -90.0 if el.rot else 0.0)


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
    if isinstance(el, (Rect, Ellipse, Polygon)):
        area = area_box(el, doc)
        if area is not None and area[1].contains(pt, tol):
            return True
    if isinstance(el, Rect):
        if el.fill and el.x - tol <= pt[0] <= el.x + el.w + tol and el.y - tol <= pt[1] <= el.y + el.h + tol:
            return True
        if any(geo.dist_to_segment(pt, a, b) <= el.width / 2 + tol for a, b in el.snap_segments()):
            return True
        return any(box.contains(pt, tol) for _t, box in rect_dim_boxes(el, doc))
    if isinstance(el, Ellipse):
        cx, cy = el.center()
        rx, ry = el.w / 2 + tol, el.h / 2 + tol
        if el.fill and rx > 0 and ry > 0 and ((pt[0] - cx) / rx) ** 2 + ((pt[1] - cy) / ry) ** 2 <= 1:
            return True
        if any(geo.dist_to_segment(pt, a, b) <= el.width / 2 + tol for a, b in el.snap_segments()):
            return True
        return any(box.contains(pt, tol) for _t, box in rect_dim_boxes(el, doc))
    if isinstance(el, Polygon):
        if el.fill and el.closed and len(el.points) > 2 and geo.point_in_polygon(pt, el.pts()):
            return True
        if any(geo.dist_to_segment(pt, a, b) <= el.width / 2 + tol for a, b in el.sides()):
            return True
        return any(box.contains(pt, tol) for _t, box in poly_length_boxes(el, doc))
    if isinstance(el, Symbol):
        lx, ly = el.to_local(pt)
        x0, y0, x1, y1 = el.local_bounds()
        return x0 - tol <= lx <= x1 + tol and y0 - tol <= ly <= y1 + tol
    if isinstance(el, Text):
        return text_box(el, doc).contains(pt, tol)
    if isinstance(el, Dimension):
        g = dim_geo(el, doc)
        if geo.dist_to_segment(pt, g.a2, g.b2) <= tol or g.box.contains(pt, tol):
            return True
        return any(geo.dist_to_segment(pt, s, e) <= tol for s, e in ((g.a, g.a2), (g.b, g.b2)))
    return False


def hit(doc: Document, pt: Point, tol: float) -> tuple[str, str] | None:
    """Elemento mais à frente sob o ponto: (id, "label" ou "body")."""
    for el in reversed(paint_order(doc)):
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
        elif isinstance(el, Polygon) and not (el.fill and el.closed):
            if any(geo.segment_touches_rect(a, b, box) for a, b in el.sides()):
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
    if isinstance(el, (Rect, Ellipse)):
        x0, y0, x1, y1 = el.x, el.y, el.x + el.w, el.y + el.h
        return [("tl", (x0, y0)), ("tr", (x1, y0)), ("br", (x1, y1)), ("bl", (x0, y1))]
    if isinstance(el, Polygon):
        return [(f"v{i}", q) for i, q in enumerate(el.pts())]
    if isinstance(el, Symbol):
        if el.in_wall():
            return [("j1", el.to_world(-el.w / 2, 0)), ("j2", el.to_world(el.w / 2, 0))]
        if el.shape == "north":
            return [("sx", el.to_world(el.w / 2, 0))]
        return [("sx", el.to_world(el.w / 2, 0)), ("sy", el.to_world(0, el.h / 2))]
    return []


def handle_anchor(el: Element, name: str) -> Point | None:
    """Ponto que fica parado enquanto a alça `name` é arrastada (para as retas a 90°)."""
    if isinstance(el, (Segment, Dimension)):
        return el.p2 if name == "p1" else el.p1 if name == "p2" else None
    if isinstance(el, (Rect, Ellipse)):
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
    elif isinstance(el, (Rect, Ellipse)):
        anchor = anchor if anchor is not None else handle_anchor(el, name)
        if anchor is not None:
            el.x, el.y, el.w, el.h = geo.rect_norm(anchor[0], anchor[1], pt[0], pt[1])
    elif isinstance(el, Polygon):
        i = int(name[1:]) if name[1:].isdigit() else -1
        if 0 <= i < len(el.points):
            el.points[i] = [pt[0], pt[1]]
    elif isinstance(el, Symbol):  # cresce igual para os dois lados
        lx, ly = el.to_local(pt)
        if name in ("j1", "j2", "sx"):
            el.w = max(2 * abs(lx), 5.0)
            if el.shape == "north":
                el.h = el.w
        elif name == "sy":
            el.h = max(2 * abs(ly), 5.0)


# ------------------------------------------------------------------------------------- encaixe
def wall_at(doc: Document, pt: Point, tol: float, exclude=()) -> tuple[Point, float, float, Seg] | None:
    """Parede perto do ponto (viga, linha ou lado de uma forma), para portas e janelas.

    Devolve o ponto no eixo da parede, o ângulo dela em graus (entre -90 e 90), a espessura e o trecho.
    """
    exclude = set(exclude)
    best = None
    bd = math.inf
    for el in doc.elements:
        if el.id in exclude:
            continue
        if isinstance(el, Segment):
            segs = [(el.p1, el.p2)]
        elif isinstance(el, (Rect, Polygon)):
            segs = el.snap_segments()
        else:
            continue
        for a, b in segs:
            if geo.dist(a, b) < 1e-6:
                continue
            q = geo.closest_on_segment(pt, a, b)
            d = geo.dist(pt, q) - el.width / 2
            if d <= tol and d < bd:
                ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
                if ang > 90 + 1e-9:
                    ang -= 180
                elif ang <= -90 + 1e-9:
                    ang += 180
                best, bd = (q, ang + 0.0, el.width, (a, b)), d
    return best


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
