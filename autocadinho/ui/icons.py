"""Ícones vetoriais desenhados com QPainter (sem arquivos externos) e o logotipo do app.

Os ícones são desenhados numa grade de 24 × 24. Para acompanhar a troca de tema, use `bind()`: ele
guarda o nome do ícone no widget e `refresh_all()` redesenha todos com as cores do tema novo.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QWidget

from . import theme

DPR = 2.0


def _pen(p: QPainter, c: QColor, w: float = 1.8) -> None:
    pen = QPen(c, w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _fill(p: QPainter, c: QColor) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(c))


def _poly(p: QPainter, *pts: tuple[float, float], close: bool = False) -> None:
    path = QPainterPath(QPointF(*pts[0]))
    for pt in pts[1:]:
        path.lineTo(QPointF(*pt))
    if close:
        path.closeSubpath()
    p.drawPath(path)


def _line(p: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _magnifier(p: QPainter, c: QColor) -> None:
    _pen(p, c)
    p.drawEllipse(QPointF(10.5, 10.5), 6.2, 6.2)
    _line(p, 15.2, 15.2, 20, 20)


def draw(name: str, p: QPainter, c: QColor) -> None:  # noqa: C901 (um ícone por ramo)
    if name == "select":
        _pen(p, c, 1.7)
        _poly(p, (6, 3.5), (6, 19), (10.2, 15), (13.2, 21), (15.8, 19.8), (12.9, 13.9), (18.6, 13.6), close=True)
    elif name == "beam":
        _fill(p, c)
        p.drawRoundedRect(QRectF(2.5, 9.2, 19, 5.6), 1.0, 1.0)
        _pen(p, c, 1.3)
        _line(p, 2.5, 5.5, 2.5, 7.5)
        _line(p, 21.5, 5.5, 21.5, 7.5)
        _line(p, 2.5, 6.5, 21.5, 6.5)
    elif name == "line":
        _pen(p, c, 1.8)
        _line(p, 5, 19, 19, 5)
        _fill(p, c)
        p.drawEllipse(QPointF(5, 19), 2.0, 2.0)
        p.drawEllipse(QPointF(19, 5), 2.0, 2.0)
    elif name == "pillar":
        _pen(p, c, 1.6)
        _line(p, 2.5, 12, 21.5, 12)
        _line(p, 12, 2.5, 12, 21.5)
        _fill(p, c)
        p.drawRect(QRectF(8.2, 6.5, 7.6, 11))
    elif name == "rect":
        _pen(p, c, 1.9)
        p.drawRoundedRect(QRectF(3.5, 6, 17, 12), 1.2, 1.2)
    elif name == "dim":
        _pen(p, c, 1.5)
        _line(p, 4, 9, 4, 19)
        _line(p, 20, 9, 20, 19)
        _line(p, 2.5, 15, 21.5, 15)
        _pen(p, c, 2.0)
        _line(p, 2.8, 16.2, 5.2, 13.8)
        _line(p, 18.8, 16.2, 21.2, 13.8)
        _pen(p, c, 1.6)
        _line(p, 8.5, 10.5, 15.5, 10.5)
    elif name == "text":
        _pen(p, c, 2.0)
        _line(p, 5.5, 5.5, 18.5, 5.5)
        _line(p, 12, 5.5, 12, 19)
        _pen(p, c, 1.6)
        _line(p, 9.5, 19, 14.5, 19)
        _line(p, 5.5, 5.5, 5.5, 7.5)
        _line(p, 18.5, 5.5, 18.5, 7.5)
    elif name == "erase":
        _pen(p, c, 1.7)
        _poly(p, (3.5, 14.5), (12.5, 5.5), (20, 13), (13, 20), (8.5, 20), close=True)
        _line(p, 8.2, 9.8, 15.7, 17.3)
        _line(p, 13, 20, 20.5, 20)
    elif name == "pan":
        _pen(p, c, 1.7)
        _line(p, 12, 3, 12, 21)
        _line(p, 3, 12, 21, 12)
        _poly(p, (9.2, 5.8), (12, 3), (14.8, 5.8))
        _poly(p, (9.2, 18.2), (12, 21), (14.8, 18.2))
        _poly(p, (5.8, 9.2), (3, 12), (5.8, 14.8))
        _poly(p, (18.2, 9.2), (21, 12), (18.2, 14.8))
    elif name == "new":
        _pen(p, c)
        _poly(p, (6, 3), (14, 3), (18.5, 7.5), (18.5, 21), (6, 21), close=True)
        _poly(p, (14, 3), (14, 7.5), (18.5, 7.5))
        _line(p, 12.2, 11, 12.2, 17)
        _line(p, 9.2, 14, 15.2, 14)
    elif name == "open":
        _pen(p, c)
        path = QPainterPath(QPointF(3, 7))
        for pt in ((3, 19), (18.5, 19), (21.5, 11), (7, 11), (4.2, 18.6)):
            path.lineTo(QPointF(*pt))
        p.drawPath(path)
        _poly(p, (3, 7), (3, 5.5), (9, 5.5), (11, 7.5), (18, 7.5), (18, 11))
    elif name == "save":
        _pen(p, c)
        _poly(p, (4, 4), (16.5, 4), (20, 7.5), (20, 20), (4, 20), close=True)
        _poly(p, (8, 4), (8, 8.5), (15, 8.5), (15, 4))
        p.drawRoundedRect(QRectF(7.5, 13, 9, 7), 0.8, 0.8)
    elif name in ("undo", "redo"):
        if name == "redo":
            p.translate(24, 0)
            p.scale(-1, 1)
        _pen(p, c)
        _poly(p, (8.5, 4.5), (4.5, 8.5), (8.5, 12.5))
        path = QPainterPath(QPointF(4.5, 8.5))
        path.lineTo(14, 8.5)
        path.cubicTo(17.6, 8.5, 20, 11, 20, 14)
        path.cubicTo(20, 17, 17.6, 19.5, 14, 19.5)
        path.lineTo(9, 19.5)
        p.drawPath(path)
    elif name == "print":
        _pen(p, c)
        _poly(p, (7, 8), (7, 3.5), (17, 3.5), (17, 8))
        p.drawRoundedRect(QRectF(3, 8, 18, 9), 2, 2)
        _poly(p, (7, 14), (17, 14), (17, 20.5), (7, 20.5), close=True)
        _fill(p, c)
        p.drawEllipse(QPointF(17.5, 11), 1.0, 1.0)
    elif name == "pdf":
        _pen(p, c)
        _poly(p, (6, 3), (14, 3), (18.5, 7.5), (18.5, 21), (6, 21), close=True)
        _poly(p, (14, 3), (14, 7.5), (18.5, 7.5))
        _line(p, 12.2, 10.5, 12.2, 17.5)
        _poly(p, (9.4, 14.8), (12.2, 17.6), (15, 14.8))
    elif name == "image":
        _pen(p, c)
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        _poly(p, (5, 17), (10, 11.5), (14, 15.5), (16, 13.5), (19.5, 17))
        p.drawEllipse(QPointF(15.5, 9), 1.5, 1.5)
    elif name == "zoom_in":
        _magnifier(p, c)
        _line(p, 10.5, 7.8, 10.5, 13.2)
        _line(p, 7.8, 10.5, 13.2, 10.5)
    elif name == "zoom_out":
        _magnifier(p, c)
        _line(p, 7.8, 10.5, 13.2, 10.5)
    elif name == "fit":
        _pen(p, c)
        for (x, y, dx, dy) in ((4, 4, 1, 1), (20, 4, -1, 1), (4, 20, 1, -1), (20, 20, -1, -1)):
            _poly(p, (x, y + 5 * dy), (x, y), (x + 5 * dx, y))
        p.drawRoundedRect(QRectF(9, 9, 6, 6), 1, 1)
    elif name == "sun":
        _pen(p, c, 1.7)
        p.drawEllipse(QPointF(12, 12), 4, 4)
        for i in range(8):
            a = math.radians(i * 45)
            _line(p, 12 + math.cos(a) * 7, 12 + math.sin(a) * 7, 12 + math.cos(a) * 9.3, 12 + math.sin(a) * 9.3)
    elif name == "moon":
        _pen(p, c, 1.7)
        big = QPainterPath()
        big.addEllipse(QPointF(11.5, 12.5), 8, 8)
        cut = QPainterPath()
        cut.addEllipse(QPointF(16.5, 8), 6.8, 6.8)
        p.drawPath(big.subtracted(cut))
    elif name == "more":
        _fill(p, c)
        for x in (5.5, 12, 18.5):
            p.drawEllipse(QPointF(x, 12), 1.8, 1.8)
    elif name == "home":
        _pen(p, c)
        _poly(p, (3, 11.5), (12, 3.8), (21, 11.5))
        _poly(p, (5.5, 9.5), (5.5, 20), (18.5, 20), (18.5, 9.5))
        _poly(p, (10, 20), (10, 14.5), (14, 14.5), (14, 20))
    elif name == "trash":
        _pen(p, c)
        _line(p, 4, 6.5, 20, 6.5)
        _poly(p, (9, 6.5), (9, 4), (15, 4), (15, 6.5))
        _poly(p, (6, 6.5), (7, 20.5), (17, 20.5), (18, 6.5))
        _line(p, 10, 10.5, 10, 16.5)
        _line(p, 14, 10.5, 14, 16.5)
    elif name == "duplicate":
        _pen(p, c)
        p.drawRoundedRect(QRectF(3.5, 8.5, 12, 12), 2, 2)
        _poly(p, (8.5, 8.5), (8.5, 5.5), (10.5, 3.5), (18.5, 3.5), (20.5, 5.5), (20.5, 13.5), (18.5, 15.5), (15.5, 15.5))
    elif name == "rotate":
        _pen(p, c)
        path = QPainterPath()
        path.arcMoveTo(QRectF(4, 4, 16, 16), 120)
        path.arcTo(QRectF(4, 4, 16, 16), 120, -300)
        p.drawPath(path)
        _poly(p, (6.2, 3.6), (8, 5.1), (6.6, 7.6))
    elif name == "grid":
        _pen(p, c, 1.5)
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 1.5, 1.5)
        for v in (9.33, 14.66):
            _line(p, v, 4, v, 20)
            _line(p, 4, v, 20, v)
    elif name == "magnet":
        _pen(p, c, 1.7)
        path = QPainterPath(QPointF(5, 4))
        path.lineTo(5, 12)
        path.cubicTo(5, 21, 19, 21, 19, 12)
        path.lineTo(19, 4)
        path.lineTo(15, 4)
        path.lineTo(15, 12)
        path.cubicTo(15, 16, 9, 16, 9, 12)
        path.lineTo(9, 4)
        path.closeSubpath()
        p.drawPath(path)
        _line(p, 5, 8, 9, 8)
        _line(p, 15, 8, 19, 8)
    elif name == "ortho":
        _pen(p, c, 1.8)
        _poly(p, (5, 3.5), (5, 19), (20.5, 19))
        _pen(p, c, 1.4)
        _poly(p, (5, 14.5), (9.5, 14.5), (9.5, 19))
    elif name == "help":
        _pen(p, c)
        p.drawEllipse(QPointF(12, 12), 9, 9)
        path = QPainterPath(QPointF(9.4, 9.6))
        path.cubicTo(9.4, 6.4, 14.6, 6.4, 14.6, 9.6)
        path.cubicTo(14.6, 11.8, 12, 12, 12, 14.2)
        p.drawPath(path)
        _fill(p, c)
        p.drawEllipse(QPointF(12, 17.3), 1.1, 1.1)
    elif name == "info":
        _pen(p, c)
        p.drawEllipse(QPointF(12, 12), 9, 9)
        _line(p, 12, 11, 12, 17)
        _fill(p, c)
        p.drawEllipse(QPointF(12, 7.6), 1.1, 1.1)
    elif name == "check":
        _pen(p, c, 2.4)
        _poly(p, (5, 12.5), (10, 17.2), (19, 7.2))
    elif name == "close":
        _pen(p, c)
        _line(p, 6, 6, 18, 18)
        _line(p, 18, 6, 6, 18)
    elif name == "chevron":
        _pen(p, c, 2.2)
        _poly(p, (6.5, 9.5), (12, 15), (17.5, 9.5))
    elif name == "plus":
        _pen(p, c, 2.0)
        _line(p, 12, 5, 12, 19)
        _line(p, 5, 12, 19, 12)
    elif name == "minus":
        _pen(p, c, 2.0)
        _line(p, 5, 12, 19, 12)
    elif name == "globe":
        _pen(p, c, 1.6)
        p.drawEllipse(QPointF(12, 12), 9, 9)
        p.drawEllipse(QPointF(12, 12), 4, 9)
        _line(p, 3, 12, 21, 12)
        _line(p, 4.6, 7.5, 19.4, 7.5)
        _line(p, 4.6, 16.5, 19.4, 16.5)
    elif name == "front":
        _pen(p, c, 1.6)
        p.drawRoundedRect(QRectF(9, 9, 11, 11), 1.5, 1.5)
        _fill(p, c)
        p.drawRoundedRect(QRectF(4, 4, 11, 11), 1.5, 1.5)
    elif name == "back":
        _fill(p, c)
        p.drawRoundedRect(QRectF(9, 9, 11, 11), 1.5, 1.5)
        _pen(p, c, 1.6)
        p.drawRoundedRect(QRectF(4, 4, 11, 11), 1.5, 1.5)
    elif name == "plan":
        _pen(p, c, 2.0)
        p.drawRect(QRectF(4, 5, 16, 14))
        _pen(p, c, 1.5)
        _line(p, 10, 5, 10, 19)
        _line(p, 10, 11, 20, 11)
        _fill(p, c)
        for x, y in ((4, 5), (20, 5), (4, 19), (20, 19), (10, 19)):
            p.drawRect(QRectF(x - 1.6, y - 1.6, 3.2, 3.2))
    elif name == "warning":
        _pen(p, c)
        _poly(p, (12, 3.5), (21, 19.5), (3, 19.5), close=True)
        _line(p, 12, 9.5, 12, 14)
        _fill(p, c)
        p.drawEllipse(QPointF(12, 16.8), 1.0, 1.0)
    elif name == "label":
        _pen(p, c, 1.7)
        _poly(p, (3.5, 7), (14, 7), (20.5, 12), (14, 17), (3.5, 17), close=True)
        _fill(p, c)
        p.drawEllipse(QPointF(14, 12), 1.3, 1.3)
    else:  # desconhecido: um quadradinho, para não quebrar
        _pen(p, c)
        p.drawRect(QRectF(5, 5, 14, 14))


def _role_color(role: str) -> QColor:
    t = theme.current()
    return QColor(getattr(t, role, None) or role)


def pixmap(name: str, color: QColor | str, size: int = 20, dpr: float = DPR) -> QPixmap:
    c = QColor(color)
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size * dpr / 24.0
    p.scale(s, s)
    draw(name, p, c)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: QColor | str | None = None, size: int = 20, on_color: QColor | str | None = None,
         disabled_color: QColor | str | None = None) -> QIcon:
    t = theme.current()
    ic = QIcon()
    ic.addPixmap(pixmap(name, color or t.text, size), QIcon.Mode.Normal, QIcon.State.Off)
    if on_color is not None:
        ic.addPixmap(pixmap(name, on_color, size), QIcon.Mode.Normal, QIcon.State.On)
        ic.addPixmap(pixmap(name, on_color, size), QIcon.Mode.Active, QIcon.State.On)
    ic.addPixmap(pixmap(name, disabled_color or t.faint, size), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic


def bind(widget: QWidget, name: str, role: str = "text", size: int = 20, on_role: str | None = None) -> None:
    """Põe o ícone `name` no botão/rótulo e o acompanha nas trocas de tema (cores por papel do tema)."""
    widget.setProperty("acIcon", name)
    widget.setProperty("acRole", role)
    widget.setProperty("acSize", size)
    widget.setProperty("acOn", on_role or "")
    _apply(widget)


def _apply(w: QWidget) -> None:
    name = w.property("acIcon")
    if not name:
        return
    role = str(w.property("acRole") or "text")
    size = int(w.property("acSize") or 20)
    on_role = str(w.property("acOn") or "")
    if isinstance(w, QLabel):
        w.setPixmap(pixmap(str(name), _role_color(role), size))
    elif isinstance(w, QAbstractButton):
        w.setIcon(icon(str(name), _role_color(role), size, _role_color(on_role) if on_role else None))
        w.setIconSize(QSize(size, size))


def refresh_all() -> None:
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        if w.property("acIcon"):
            _apply(w)


# ------------------------------------------------------------------------------------- logotipo
def paint_logo(p: QPainter, size: float) -> None:
    """Logotipo: quadrado laranja arredondado com uma planta branca (vigas e pilares)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    m = size * 0.04
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#f6a25a"))
    grad.setColorAt(1.0, QColor("#e0582a"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(m, m, size - 2 * m, size - 2 * m), size * 0.22, size * 0.22)
    s = size / 24.0
    p.scale(s, s)
    white = QColor("#ffffff")
    pen = QPen(white, 2.1)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(5.5, 6.5, 13, 11))
    pen.setWidthF(1.5)
    p.setPen(pen)
    p.drawLine(QPointF(10.5, 6.5), QPointF(10.5, 17.5))
    p.drawLine(QPointF(10.5, 12), QPointF(18.5, 12))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(white))
    for x, y in ((5.5, 6.5), (18.5, 6.5), (5.5, 17.5), (18.5, 17.5), (10.5, 17.5), (10.5, 6.5)):
        p.drawRect(QRectF(x - 1.55, y - 1.55, 3.1, 3.1))
    p.restore()


def logo_pixmap(size: int, dpr: float = DPR) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    paint_logo(p, size * dpr)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(s, s)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        paint_logo(p, s)
        p.end()
        ic.addPixmap(pm)
    return ic
