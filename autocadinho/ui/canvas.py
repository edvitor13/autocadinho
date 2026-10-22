"""Área de desenho: mostra o documento sobre a grade e cuida das ferramentas (mouse e teclado).

Coordenadas: o documento está em centímetros; na tela, `x_tela = x * scale + ox` (scale = pixels
por centímetro). 100% de zoom = 1 pixel por centímetro.

A área de desenho muda o documento direto e avisa com `changed(chave)` quando um passo termina
(soltar o mouse, apertar Enter...). Quem guarda o histórico é a janela principal.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLineEdit, QWidget

from .. import geometry as geo
from .. import render
from ..geometry import Point
from ..i18n import _
from ..model import (SYMBOLS, Beam, Dimension, Document, Element, Ellipse, Labeled, Line, Pillar, Polygon, Rect, Segment,
                     Symbol, Text, new_id, selection_center)
from . import theme

TOOLS = ("select", "beam", "line", "pillar", "rect", "ellipse", "triangle", "poly", "dim", "text", "symbol", "erase",
         "pan")
DRAW_TOOLS = ("beam", "line", "rect", "ellipse", "triangle", "dim")  # clique e arraste (ou dois cliques)
BOX_TOOLS = ("rect", "ellipse", "triangle")  # de um canto ao outro; Shift faz quadrado
MIN_SCALE, MAX_SCALE = 0.02, 40.0
HANDLE_PX = 10
SNAP_PX = 10
CLICK_PX = 4
MIME = "application/x-autocadinho"


class _InlineEditor(QLineEdit):
    """Caixa de texto que aparece em cima do desenho para escrever um texto ou um nome."""

    def __init__(self, canvas: "Canvas", el_id: str, field: str, is_new: bool) -> None:
        super().__init__(canvas)
        self.setObjectName("Inline")
        self.canvas = canvas
        self.el_id = el_id
        self.field = field
        self.is_new = is_new

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() == Qt.Key.Key_Escape:
            self.canvas.finish_editor(False)
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.canvas.finish_editor(True)
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e) -> None:  # noqa: N802
        super().focusOutEvent(e)
        if self.canvas._editor is self:
            self.canvas.finish_editor(True)


class Canvas(QWidget):
    changed = Signal(str)  # o desenho mudou (a chave junta passos seguidos no histórico)
    selectionChanged = Signal()
    cursorMoved = Signal(object)  # Point ou None
    viewChanged = Signal()
    toolChanged = Signal(str)
    hintChanged = Signal(str)
    contextRequested = Signal(QPoint)
    editRequested = Signal(str)  # texto com várias linhas: editar no painel

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = Document()
        self.selection: list[str] = []
        self.tool = "select"
        self.scale = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self.show_grid = True
        self.snap_on = True
        self.ortho_on = True
        self._drag: SimpleNamespace | None = None
        self._draw_start: Point | None = None
        self._draw_press = QPointF()
        self._click_mode = False
        self._preview: Element | None = None
        self._hover_id: str | None = None
        self._rubber_ids: list[str] = []
        self._snap_mark: tuple[Point, str] | None = None
        self._last_pos: QPointF | None = None
        self._space = False
        self._editor: _InlineEditor | None = None
        self._pillar_turned = False
        self._poly_pts: list[Point] = []  # cantos já clicados do polígono
        self.symbol_shape = "door"  # símbolo da ferramenta Símbolos
        self._sym_turn = 0  # giros de 90° do próximo símbolo (tecla R)
        self._fitted = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(320, 240)
        self._update_cursor()

    # ------------------------------------------------------------------------------ coordenadas
    def to_world(self, pos: QPointF) -> Point:
        return ((pos.x() - self.ox) / self.scale, (pos.y() - self.oy) / self.scale)

    def to_screen(self, pt: Point) -> QPointF:
        return QPointF(pt[0] * self.scale + self.ox, pt[1] * self.scale + self.oy)

    def _tol(self, px: float = SNAP_PX) -> float:
        return px / self.scale

    def zoom_percent(self) -> int:
        return round(self.scale * 100)

    # ------------------------------------------------------------------------------ documento
    def set_document(self, doc: Document, fit: bool = True) -> None:
        self.cancel_operation()
        self.doc = doc
        self.selection = []
        self._hover_id = None
        if fit:
            if self.width() > 0 and self.isVisible():
                self.fit()
            else:
                self._fitted = False
        self.selectionChanged.emit()
        self.update()

    def selected_elements(self) -> list[Element]:
        out = []
        for i in self.selection:
            el = self.doc.get(i)
            if el is not None:
                out.append(el)
        return out

    def set_selection(self, ids) -> None:
        ids = [i for i in ids if self.doc.get(i) is not None]
        if ids != self.selection:
            self.selection = ids
            self.selectionChanged.emit()
        self.update()

    def prune_selection(self) -> None:
        self.set_selection([i for i in self.selection if self.doc.get(i) is not None])

    # ------------------------------------------------------------------------------ vista
    def fit(self) -> None:
        b = render.document_bounds(self.doc)
        if b is None or (b.width() < 1 and b.height() < 1):
            b = QRectF(0, 0, 1000, 600)
        m = 56
        w, h = max(self.width(), 200), max(self.height(), 200)
        s = min((w - 2 * m) / max(b.width(), 1.0), (h - 2 * m) / max(b.height(), 1.0))
        self.scale = min(max(s, MIN_SCALE), MAX_SCALE)
        c = b.center()
        self.ox = w / 2 - c.x() * self.scale
        self.oy = h / 2 - c.y() * self.scale
        self._fitted = True
        self.viewChanged.emit()
        self.update()

    def zoom_at(self, factor: float, pos: QPointF | None = None) -> None:
        if pos is None:
            pos = QPointF(self.width() / 2, self.height() / 2)
        w = self.to_world(pos)
        self.scale = min(max(self.scale * factor, MIN_SCALE), MAX_SCALE)
        self.ox = pos.x() - w[0] * self.scale
        self.oy = pos.y() - w[1] * self.scale
        self.viewChanged.emit()
        self.update()

    def view_state(self) -> tuple[float, float, float]:
        return (self.scale, self.ox, self.oy)

    def set_view_state(self, state: tuple[float, float, float]) -> None:
        self.scale, self.ox, self.oy = state
        self._fitted = True
        self.viewChanged.emit()
        self.update()

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if not self._fitted:
            self.fit()

    def resizeEvent(self, e) -> None:  # noqa: N802
        old = e.oldSize()
        if self._fitted and old.width() > 0 and old.height() > 0:
            self.ox += (e.size().width() - old.width()) / 2
            self.oy += (e.size().height() - old.height()) / 2
        super().resizeEvent(e)

    # ------------------------------------------------------------------------------ ferramentas
    def set_tool(self, name: str) -> None:
        if name not in TOOLS:
            return
        self.finish_editor(True)
        self.cancel_operation()
        self.tool = name
        self._preview = None
        self._hover_id = None
        self._snap_mark = None
        self._update_cursor()
        self.toolChanged.emit(name)
        self.hintChanged.emit(self.hint())
        self.update()

    def set_symbol(self, shape: str) -> None:
        """Escolhe o símbolo (porta, janela...) e liga a ferramenta Símbolos."""
        if shape in SYMBOLS:
            self.symbol_shape = shape
            self._sym_turn = 0
            if self.tool == "symbol":
                self.toolChanged.emit("symbol")
                self.hintChanged.emit(self.hint())
            else:
                self.set_tool("symbol")

    def hint(self) -> str:
        drawing = self._draw_start is not None
        t = self.tool
        if t == "select":
            return _("Clique num desenho para escolher. Arraste para mover. Duplo clique muda o nome ou o texto.")
        if t == "beam":
            return _("Solte (ou clique) onde a viga termina. Esc cancela.") if drawing else \
                _("Clique e arraste para desenhar a viga. Segure Shift para fazer inclinada.")
        if t == "line":
            return _("Solte (ou clique) onde a linha termina. Esc cancela.") if drawing else \
                _("Clique e arraste para desenhar a linha. Segure Shift para fazer inclinada.")
        if t == "pillar":
            return _("Clique para colocar o pilar. A tecla R deixa o pilar em pé ou deitado.")
        if t == "rect":
            return _("Solte (ou clique) no outro canto. Shift faz um quadrado.") if drawing else \
                _("Clique e arraste de um canto ao outro.")
        if t == "ellipse":
            return _("Solte (ou clique) no outro canto. Shift faz um círculo perfeito.") if drawing else \
                _("Clique e arraste de um canto ao outro, como no Paint. Shift faz um círculo perfeito.")
        if t == "triangle":
            return _("Solte (ou clique) no outro canto. Depois, as bolinhas mudam cada ponta.") if drawing else \
                _("Clique e arraste de um canto ao outro para fazer o triângulo.")
        if t == "poly":
            if self._poly_pts:
                return _("Clique no próximo canto. Para terminar, clique no primeiro ponto, dê dois cliques ou aperte "
                         "Enter. Backspace desfaz o último ponto.")
            return _("Clique em cada canto da forma, um depois do outro. Segure Shift para lados inclinados.")
        if t == "symbol":
            name = _(SYMBOLS[self.symbol_shape][0])
            if self.symbol_shape in ("door", "door2", "sliding", "window"):
                return _("{nome}: clique em cima de uma viga ou linha para colocar na parede. A tecla R vira o lado.") \
                    .format(nome=name)
            return _("{nome}: clique para colocar. A tecla R gira.").format(nome=name)
        if t == "dim":
            return _("Solte (ou clique) onde a medida termina.") if drawing else \
                _("Clique e arraste do começo ao fim do que quer medir.")
        if t == "text":
            return _("Clique onde o texto vai ficar e escreva. Enter confirma.")
        if t == "erase":
            return _("Clique no que quer apagar. Pode arrastar por cima de vários.")
        return _("Arraste para mover a folha. A rodinha do mouse aproxima e afasta.")

    def _update_cursor(self) -> None:
        if self._space or self.tool == "pan":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.tool in DRAW_TOOLS or self.tool in ("pillar", "text", "poly", "symbol"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.tool == "erase":
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def cancel_operation(self) -> None:
        """Cancela o que estiver no meio (desenho começado, arraste)."""
        d = self._drag
        if d is not None:
            if d.mode == "move" and d.moved:
                for el in self.selected_elements():
                    el.move(-d.applied[0], -d.applied[1])
            elif d.mode in ("handle", "label") and d.moved:
                self._restore(d.orig)
        self._drag = None
        self._draw_start = None
        self._click_mode = False
        self._poly_pts = []
        self._preview = None
        self._rubber_ids = []
        self._snap_mark = None
        self.hintChanged.emit(self.hint())
        self.update()

    def _restore(self, data: dict) -> None:
        for i, el in enumerate(self.doc.elements):
            if el.id == data.get("id"):
                self.doc.elements[i] = Element.from_dict(data)
                return

    def escape(self) -> None:
        if self._editor is not None:
            self.finish_editor(False)
        elif self._draw_start is not None or self._drag is not None or self._poly_pts:
            self.cancel_operation()
        elif self.selection:
            self.set_selection([])
        elif self.tool != "select":
            self.set_tool("select")

    # ------------------------------------------------------------------------------ encaixe
    def snap_point(self, w: Point, start: Point | None = None, ortho: bool = False, exclude=()) -> Point:
        mods = QGuiApplication.keyboardModifiers()
        free = bool(mods & Qt.KeyboardModifier.AltModifier)
        use_ortho = ortho and start is not None and (self.ortho_on != bool(mods & Qt.KeyboardModifier.ShiftModifier))
        raw = w
        axis_h = True
        if use_ortho and start is not None:
            axis_h = abs(w[0] - start[0]) >= abs(w[1] - start[1])
            raw = geo.ortho(start, w)
        if self.snap_on and not free:
            pts, segs = render.snap_sources(self.doc, exclude)
            s = geo.snap(raw, pts, segs, self._tol(), self.doc.snap_step)
        else:
            s = geo.Snap(raw, "none")
        pt = s.point
        if use_ortho and start is not None:
            pt = (pt[0], start[1]) if axis_h else (start[0], pt[1])
        self._snap_mark = (pt, s.kind) if s.kind in ("point", "line") else None
        return pt

    # ------------------------------------------------------------------------------ mouse
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if self._editor is not None:
            self.finish_editor(True)
        self.setFocus()
        pos = e.position()
        w = self.to_world(pos)
        btn = e.button()
        if btn == Qt.MouseButton.MiddleButton or (btn == Qt.MouseButton.LeftButton and (self._space or self.tool == "pan")):
            self._drag = SimpleNamespace(mode="pan", press=pos, ox=self.ox, oy=self.oy, moved=False)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if btn != Qt.MouseButton.LeftButton:
            return
        mods = e.modifiers()
        if self.tool in DRAW_TOOLS:
            self._press_draw(pos, w)
        elif self.tool == "select":
            self._press_select(pos, w, mods)
        elif self.tool == "pillar":
            self._place_pillar(w)
        elif self.tool == "poly":
            self._press_poly(pos, w)
        elif self.tool == "symbol":
            self._place_symbol(w)
        elif self.tool == "text":
            self._place_text(w)
        elif self.tool == "erase":
            self._drag = SimpleNamespace(mode="erase", press=pos, erased=False, moved=False)
            self._erase_at(w)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        pos = e.position()
        self._last_pos = pos
        w = self.to_world(pos)
        self.cursorMoved.emit(w)
        d = self._drag
        if d is not None and d.mode == "pan":
            self.ox = d.ox + pos.x() - d.press.x()
            self.oy = d.oy + pos.y() - d.press.y()
            self.viewChanged.emit()
            self.update()
            return
        if self.tool in DRAW_TOOLS and self._draw_start is not None:
            self._set_preview_end(self._draw_end(w))
            self.update()
            return
        if self.tool == "poly" and self._poly_pts:
            self._poly_preview(self._poly_next(w))
            self.update()
            return
        if d is None:
            self._hover(pos, w)
            return
        if d.mode == "move":
            self._drag_move(pos, w, d)
        elif d.mode == "label":
            self._drag_label(pos, w, d)
        elif d.mode == "handle":
            self._drag_handle(w, d)
        elif d.mode == "rubber":
            d.cur = pos
            r = QRectF(self.to_world_point(d.press), self.to_world_point(pos))
            self._rubber_ids = render.touching(self.doc, r)
        elif d.mode == "erase":
            self._erase_at(w)
        self.update()

    def to_world_point(self, pos: QPointF) -> QPointF:
        x, y = self.to_world(pos)
        return QPointF(x, y)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        pos = e.position()
        if e.button() == Qt.MouseButton.LeftButton and self.tool in DRAW_TOOLS and self._draw_start is not None:
            if not self._click_mode and (pos - self._draw_press).manhattanLength() < CLICK_PX:
                self._click_mode = True  # foi um clique: espera o segundo clique
                return
            if not self._click_mode:
                self._finish_draw(self.to_world(pos))
            return
        d = self._drag
        if d is None:
            return
        self._drag = None
        if d.mode == "pan":
            self._update_cursor()
        elif d.mode == "move" and d.moved:
            self.changed.emit("move")
        elif d.mode == "label" and d.moved:
            self.changed.emit("label-move")
        elif d.mode == "handle" and d.moved:
            self.changed.emit("handle")
        elif d.mode == "rubber":
            ids = list(self._rubber_ids)
            self._rubber_ids = []
            if d.additive:
                ids = d.base + [i for i in ids if i not in d.base]
            self.set_selection(ids)
        elif d.mode == "erase" and d.erased:
            self.prune_selection()
            self.changed.emit("erase")
        self._snap_mark = None
        self.update()

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool == "poly":
            self._finish_poly()
            return
        if self.tool != "select":
            self.mousePressEvent(e)
            return
        found = render.hit(self.doc, self.to_world(e.position()), self._tol(6))
        if not found:
            return
        el = self.doc.get(found[0])
        self._drag = None
        if isinstance(el, Text):
            self.edit_text(el.id, "text")
        elif isinstance(el, Dimension):
            self.edit_text(el.id, "dim")
        elif isinstance(el, Labeled):
            self.edit_text(el.id, "label")

    def contextMenuEvent(self, e) -> None:  # noqa: N802
        if self._draw_start is not None or self._drag is not None or self._poly_pts:
            self.cancel_operation()
            return
        found = render.hit(self.doc, self.to_world(QPointF(e.pos())), self._tol(6))
        if found and found[0] not in self.selection:
            self.set_selection([found[0]])
        self.contextRequested.emit(e.globalPos())

    def wheelEvent(self, e) -> None:  # noqa: N802
        if self._editor is not None:
            self.finish_editor(True)
        d = e.angleDelta()
        delta = d.y() or d.x()
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.ox += delta / 2
            self.viewChanged.emit()
            self.update()
            return
        self.zoom_at(1.0015 ** delta, e.position())

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.cursorMoved.emit(None)
        if self.tool in ("pillar", "symbol") or self._hover_id:
            self._preview = None if self.tool in ("pillar", "symbol") else self._preview
            self._hover_id = None
            self._snap_mark = None
            self.update()
        super().leaveEvent(e)

    # -- seleção e arraste
    def _press_select(self, pos: QPointF, w: Point, mods) -> None:
        additive = bool(mods & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier))
        if len(self.selection) == 1 and not additive:
            el = self.doc.get(self.selection[0])
            name = self._handle_at(el, pos) if el is not None else None
            if el is not None and name:
                self._drag = SimpleNamespace(mode="handle", id=el.id, name=name, anchor=render.handle_anchor(el, name),
                                             orig=el.to_dict(), moved=False, press=pos)
                return
        found = render.hit(self.doc, w, self._tol(6))
        if found:
            el_id, part = found
            if additive:
                sel = list(self.selection)
                if el_id in sel:
                    sel.remove(el_id)
                else:
                    sel.append(el_id)
                self.set_selection(sel)
                if el_id in self.selection:
                    self._start_move(pos, w, el_id)
                return
            if el_id not in self.selection:
                self.set_selection([el_id])
            if part == "label" and len(self.selection) == 1:
                el = self.doc.get(el_id)
                self._drag = SimpleNamespace(mode="label", id=el_id, press=pos, press_w=w, moved=False,
                                             orig=el.to_dict() if el else {}, start=(0.0, 0.0))
            else:
                self._start_move(pos, w, el_id)
            return
        if not additive and self.selection:
            self.set_selection([])
        self._drag = SimpleNamespace(mode="rubber", press=pos, cur=pos, additive=additive, base=list(self.selection))

    def _start_move(self, pos: QPointF, w: Point, el_id: str) -> None:
        el = self.doc.get(el_id)
        if el is None:
            return
        kps = el.key_points() or [el.center()]
        ref = min(kps, key=lambda q: geo.dist(q, w))
        self._drag = SimpleNamespace(mode="move", press=pos, press_w=w, ref=ref, applied=(0.0, 0.0), moved=False)

    def _drag_move(self, pos: QPointF, w: Point, d: SimpleNamespace) -> None:
        if not d.moved and (pos - d.press).manhattanLength() < CLICK_PX:
            return
        d.moved = True
        shift = bool(QGuiApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        raw = (d.ref[0] + w[0] - d.press_w[0], d.ref[1] + w[1] - d.press_w[1])
        if shift:
            raw = geo.ortho(d.ref, raw)
        target = self.snap_point(raw, exclude=self.selection)
        if shift:
            target = geo.ortho(d.ref, target)
        tx, ty = target[0] - d.ref[0], target[1] - d.ref[1]
        dx, dy = tx - d.applied[0], ty - d.applied[1]
        if abs(dx) > 1e-9 or abs(dy) > 1e-9:
            for el in self.selected_elements():
                el.move(dx, dy)
            d.applied = (tx, ty)

    def _drag_label(self, pos: QPointF, w: Point, d: SimpleNamespace) -> None:
        el = self.doc.get(d.id)
        if el is None or not isinstance(el, Labeled):
            return
        if not d.moved:
            if (pos - d.press).manhattanLength() < CLICK_PX:
                return
            render.materialize_label(el, self.doc)
            d.start = (el.label_dx or 0.0, el.label_dy or 0.0)
            d.moved = True
        el.label_dx = d.start[0] + w[0] - d.press_w[0]
        el.label_dy = d.start[1] + w[1] - d.press_w[1]

    def _drag_handle(self, w: Point, d: SimpleNamespace) -> None:
        el = self.doc.get(d.id)
        if el is None:
            return
        if d.name == "offset":
            pt = w
            self._snap_mark = None
        elif isinstance(el, (Segment, Dimension)):
            pt = self.snap_point(w, start=d.anchor, ortho=True, exclude={el.id})
        else:
            pt = self.snap_point(w, exclude={el.id})
            if d.anchor is not None and QGuiApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
                pt = self._square(d.anchor, pt)
        render.apply_handle(el, d.name, pt, d.anchor)
        d.moved = True

    @staticmethod
    def _square(a: Point, b: Point) -> Point:
        s = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        return (a[0] + math.copysign(s, b[0] - a[0] or 1), a[1] + math.copysign(s, b[1] - a[1] or 1))

    def _handle_at(self, el: Element, pos: QPointF) -> str | None:
        for name, pt in render.handles(el, self.doc):
            q = self.to_screen(pt)
            if abs(q.x() - pos.x()) <= HANDLE_PX and abs(q.y() - pos.y()) <= HANDLE_PX:
                return name
        return None

    def _hover(self, pos: QPointF, w: Point) -> None:
        if self.tool == "select":
            if len(self.selection) == 1:
                el = self.doc.get(self.selection[0])
                if el is not None and self._handle_at(el, pos):
                    self.setCursor(Qt.CursorShape.CrossCursor)
                    return
            found = render.hit(self.doc, w, self._tol(6))
            self.setCursor(Qt.CursorShape.SizeAllCursor if found else Qt.CursorShape.ArrowCursor)
            if self._space:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.tool == "erase":
            found = render.hit(self.doc, w, self._tol(6))
            hid = found[0] if found else None
            if hid != self._hover_id:
                self._hover_id = hid
                self.update()
        elif self.tool == "pillar":
            self._preview = self._pillar_ghost(w)
            self.update()
        elif self.tool == "symbol":
            self._preview = self._symbol_ghost(w)
            self.update()
        elif self.tool in DRAW_TOOLS or self.tool in ("text", "poly"):
            self.snap_point(w)
            self.update()

    # -- ferramentas de desenho
    def _press_draw(self, pos: QPointF, w: Point) -> None:
        if self._draw_start is None:
            start = self.snap_point(w)
            self._draw_start = start
            self._draw_press = pos
            self._click_mode = False
            self._preview = self._make(start, start)
            self.hintChanged.emit(self.hint())
            self.update()
        else:
            self._finish_draw(w)

    def _draw_end(self, w: Point) -> Point:
        start = self._draw_start or w
        if self.tool in BOX_TOOLS:
            pt = self.snap_point(w)
            if QGuiApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
                pt = self._square(start, pt)
            return pt
        return self.snap_point(w, start=start, ortho=True)

    def _make(self, a: Point, b: Point) -> Element:
        if self.tool == "beam":
            return Beam(x1=a[0], y1=a[1], x2=b[0], y2=b[1], width=self.doc.beam_width)
        if self.tool == "line":
            return Line(x1=a[0], y1=a[1], x2=b[0], y2=b[1], width=max(1.0, round(self.doc.label_size * 0.12, 1)))
        thin = max(1.0, round(self.doc.label_size * 0.12, 1))
        if self.tool in BOX_TOOLS:
            x, y, w, h = geo.rect_norm(a[0], a[1], b[0], b[1])
            if self.tool == "ellipse":
                return Ellipse(x=x, y=y, w=w, h=h, width=thin)
            if self.tool == "triangle":  # de pé dentro do retângulo, como no Paint
                return Polygon(points=[[x, y + h], [x + w / 2, y], [x + w, y + h]], width=thin)
            return Rect(x=x, y=y, w=w, h=h, width=thin)
        return Dimension(x1=a[0], y1=a[1], x2=b[0], y2=b[1], offset=round(self.doc.label_size * 2.4))

    def _set_preview_end(self, end: Point) -> None:
        if self._draw_start is None:
            return
        self._preview = self._make(self._draw_start, end)

    def _finish_draw(self, w: Point) -> None:
        if self._draw_start is None:
            return
        el = self._make(self._draw_start, self._draw_end(w))
        self._draw_start = None
        self._click_mode = False
        self._preview = None
        self._snap_mark = None
        if isinstance(el, (Rect, Ellipse)):
            ok = el.w >= 1 and el.h >= 1
        elif isinstance(el, Polygon):
            r = render.element_bounds(el, self.doc)
            ok = r.width() - el.width >= 1 and r.height() - el.width >= 1
        else:
            ok = el.length() >= 1  # type: ignore[union-attr]
        if ok:
            if isinstance(el, Beam):
                el.label = self.doc.next_label(self.doc.beam_prefix)
            self.doc.add(el)
            self.set_selection([el.id])
            self.changed.emit("add")
        self.hintChanged.emit(self.hint())
        self.update()

    def _pillar_ghost(self, w: Point) -> Pillar:
        pt = self.snap_point(w)
        pw, ph = self.doc.pillar_w, self.doc.pillar_h
        if self._pillar_turned:
            pw, ph = ph, pw
        return Pillar(x=pt[0], y=pt[1], w=pw, h=ph)

    def turn_pillar_ghost(self) -> None:
        """Alterna o próximo pilar entre em pé e deitado (tecla R com a ferramenta Pilar)."""
        self._pillar_turned = not self._pillar_turned
        if self._last_pos is not None:
            self._preview = self._pillar_ghost(self.to_world(self._last_pos))
        self.update()

    def _place_pillar(self, w: Point) -> None:
        p = self._pillar_ghost(w)
        p.label = self.doc.next_label(self.doc.pillar_prefix)
        self.doc.add(p)
        self.set_selection([p.id])
        self.changed.emit("add")

    # -- polígono, ponto a ponto
    def _poly_next(self, w: Point) -> Point:
        last = self._poly_pts[-1] if self._poly_pts else None
        return self.snap_point(w, start=last, ortho=last is not None)

    def _poly_preview(self, cursor: Point | None) -> None:
        pts = list(self._poly_pts) + ([cursor] if cursor is not None else [])
        self._preview = Polygon(points=[list(q) for q in pts], closed=len(pts) > 2,
                                width=max(1.0, round(self.doc.label_size * 0.12, 1)))

    def _press_poly(self, pos: QPointF, w: Point) -> None:
        if len(self._poly_pts) >= 3:
            first = self.to_screen(self._poly_pts[0])
            if abs(first.x() - pos.x()) <= SNAP_PX and abs(first.y() - pos.y()) <= SNAP_PX:
                self._finish_poly()
                return
        pt = self._poly_next(w)
        if self._poly_pts and geo.dist(pt, self._poly_pts[-1]) < 1e-6:
            return
        self._poly_pts.append(pt)
        self._poly_preview(None)
        self.hintChanged.emit(self.hint())
        self.update()

    def undo_poly_point(self) -> bool:
        """Tira o último canto clicado do polígono (Backspace)."""
        if not self._poly_pts:
            return False
        self._poly_pts.pop()
        cursor = self._poly_next(self.to_world(self._last_pos)) if self._last_pos is not None else None
        self._poly_preview(cursor if self._poly_pts else None)
        if not self._poly_pts:
            self._preview = None
        self.hintChanged.emit(self.hint())
        self.update()
        return True

    def _finish_poly(self) -> None:
        pts = list(self._poly_pts)
        self.cancel_operation()
        if len(pts) < 3:
            return
        el = Polygon(points=[list(q) for q in pts], width=max(1.0, round(self.doc.label_size * 0.12, 1)))
        self.doc.add(el)
        self.set_selection([el.id])
        self.changed.emit("add")

    # -- símbolos
    def _symbol_ghost(self, w: Point) -> Symbol:
        shape = self.symbol_shape if self.symbol_shape in SYMBOLS else "door"
        _name, sw, sh = SYMBOLS[shape]
        sym = Symbol(shape=shape, w=sw, h=sh, angle=90.0 * self._sym_turn)
        free = bool(QGuiApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)
        if sym.in_wall() and self.snap_on and not free:
            wall = render.wall_at(self.doc, w, self._tol(14))
            if wall is not None:
                q, ang, thick, (a, b) = wall
                step = self.doc.snap_step
                if step > 0 and abs(a[1] - b[1]) < 1e-6:
                    q = (min(max(geo.snap_value(q[0], step), min(a[0], b[0])), max(a[0], b[0])), q[1])
                elif step > 0 and abs(a[0] - b[0]) < 1e-6:
                    q = (q[0], min(max(geo.snap_value(q[1], step), min(a[1], b[1])), max(a[1], b[1])))
                sym.x, sym.y = q
                sym.angle = ang + 180.0 * (self._sym_turn % 2)
                sym.wall = thick
                self._snap_mark = (q, "line")
                return sym
        sym.x, sym.y = self.snap_point(w)
        return sym

    def turn_symbol_ghost(self) -> None:
        """Gira o próximo símbolo 90° (na parede, vira para o outro lado). Tecla R com a ferramenta Símbolos."""
        self._sym_turn = (self._sym_turn + 1) % 4
        if self._last_pos is not None:
            self._preview = self._symbol_ghost(self.to_world(self._last_pos))
        self.update()

    def _place_symbol(self, w: Point) -> None:
        sym = self._symbol_ghost(w)
        self.doc.add(sym)
        self.set_selection([sym.id])
        self.changed.emit("add")

    def _place_text(self, w: Point) -> None:
        pt = self.snap_point(w)
        t = Text(x=pt[0], y=pt[1], text="", size=self.doc.label_size)
        self.doc.add(t)
        self.set_selection([t.id])
        self.edit_text(t.id, "text", is_new=True)

    def _erase_at(self, w: Point) -> None:
        found = render.hit(self.doc, w, self._tol(6))
        if found and self._drag is not None:
            self.doc.remove([found[0]])
            self._drag.erased = True
            self._hover_id = None
            self.update()

    # ------------------------------------------------------------------------------ teclado
    def keyPressEvent(self, e) -> None:  # noqa: N802
        k = e.key()
        if k == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._space = True
            self._update_cursor()
            return
        if k == Qt.Key.Key_Escape:
            self.escape()
            return
        if self.tool == "poly" and self._poly_pts:
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._finish_poly()
                return
            if k == Qt.Key.Key_Backspace:
                self.undo_poly_point()
                return
        arrows = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0), Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        if k in arrows and self.selection:
            step = self.doc.snap_step if self.snap_on and self.doc.snap_step > 0 else 1.0
            if e.modifiers() & Qt.KeyboardModifier.AltModifier:
                step = 1.0
            elif e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step *= 10
            dx, dy = arrows[k]
            for el in self.selected_elements():
                el.move(dx * step, dy * step)
            self.changed.emit("nudge")
            self.update()
            return
        if k == Qt.Key.Key_R and not e.modifiers():
            if self.tool == "pillar":
                self.turn_pillar_ghost()
            elif self.tool == "symbol":
                self.turn_symbol_ghost()
            elif self.selection:
                self.rotate_selection()
            return
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selection:
            self.delete_selection()
            return
        if k in (Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Control):
            self._refresh_from_cursor()
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e) -> None:  # noqa: N802
        k = e.key()
        if k == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._space = False
            self._update_cursor()
            return
        if k in (Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Control):
            self._refresh_from_cursor()
        super().keyReleaseEvent(e)

    def _refresh_from_cursor(self) -> None:
        if self._last_pos is None:
            return
        w = self.to_world(self._last_pos)
        if self.tool in DRAW_TOOLS and self._draw_start is not None:
            self._set_preview_end(self._draw_end(w))
        elif self.tool == "poly" and self._poly_pts:
            self._poly_preview(self._poly_next(w))
        elif self.tool == "symbol":
            self._preview = self._symbol_ghost(w)
        else:
            return
        self.update()

    def focusOutEvent(self, e) -> None:  # noqa: N802
        self._space = False
        super().focusOutEvent(e)

    # ------------------------------------------------------------------------------ edição no lugar
    def edit_text(self, el_id: str, field: str, is_new: bool = False) -> None:
        el = self.doc.get(el_id)
        if el is None:
            return
        family = self.doc.font
        if field == "text" and isinstance(el, Text):
            current, size, center = el.text, el.size, (el.x, el.y)
            family = el.font or self.doc.font
            if "\n" in current:
                self.editRequested.emit(el_id)
                return
        elif field == "label" and isinstance(el, Labeled):
            current, size = el.label, self.doc.label_size
            el.label_visible = True
            box = render.label_box(el, self.doc)
            center = (box.cx, box.cy) if box else el.label_anchor()
        elif field == "dim" and isinstance(el, Dimension):
            g = render.dim_geo(el, self.doc)
            current, size, center = g.text, g.size, (g.box.cx, g.box.cy)
        else:
            return
        self.finish_editor(True)
        ed = _InlineEditor(self, el_id, field, is_new)
        f = QFont(ed.font())
        if family:
            f.setFamily(family)
        f.setPixelSize(int(min(max(size * self.scale * 0.9, 13), 40)))
        ed.setFont(f)
        ed.setText(current)
        ed.selectAll()
        fm = QFontMetricsF(f)
        width = int(max(160, fm.horizontalAdvance(current or "M") + 48))
        height = int(fm.height() + 14)
        c = self.to_screen(center)
        ed.setGeometry(int(c.x() - width / 2), int(c.y() - height / 2), width, height)
        self._editor = ed
        ed.show()
        ed.setFocus()

    def finish_editor(self, accept: bool) -> None:
        ed = self._editor
        if ed is None:
            return
        self._editor = None
        text = ed.text()
        ed.hide()
        ed.deleteLater()
        el = self.doc.get(ed.el_id)
        if el is None:
            return
        if ed.field == "text" and isinstance(el, Text):
            if not accept or not text.strip():
                if ed.is_new or (accept and not text.strip()):
                    self.doc.remove([el.id])
                    self.prune_selection()
                    if not ed.is_new:
                        self.changed.emit("delete")
            else:
                el.text = text
                self.changed.emit("add" if ed.is_new else "text")
        elif accept and ed.field == "label" and isinstance(el, Labeled):
            el.label = text.strip()
            self.changed.emit("label")
        elif accept and ed.field == "dim" and isinstance(el, Dimension):
            auto = render.fmt_len(el.length(), self.doc)
            el.text = "" if text.strip() in ("", auto) else text.strip()
            self.changed.emit("dim-text")
        self.setFocus()
        self.update()

    # ------------------------------------------------------------------------------ operações
    def delete_selection(self) -> bool:
        if not self.selection:
            return False
        self.doc.remove(self.selection)
        self.set_selection([])
        self.changed.emit("delete")
        return True

    def _renumber(self, el: Element) -> None:
        """Cópias de vigas e pilares com nome automático ganham o próximo número livre."""
        bp, pp = self.doc.beam_prefix, self.doc.pillar_prefix
        if isinstance(el, Beam) and bp and el.label.upper().startswith(bp.upper()):
            el.label = self.doc.next_label(bp)
        elif isinstance(el, Pillar) and pp and el.label.upper().startswith(pp.upper()):
            el.label = self.doc.next_label(pp)

    def paste_elements(self, items: list[dict], offset: Point) -> list[str]:
        ids = []
        for data in items:
            try:
                el = Element.from_dict(data)
            except ValueError:
                continue
            el.id = new_id()
            el.move(*offset)
            self._renumber(el)
            self.doc.add(el)
            ids.append(el.id)
        if ids:
            self.set_selection(ids)
            self.changed.emit("paste")
        return ids

    def duplicate_selection(self) -> None:
        step = max(self.doc.snap_step, 10.0) * 3
        self.paste_elements([el.to_dict() for el in self.selected_elements()], (step, step))

    def copy_selection(self) -> bool:
        els = self.selected_elements()
        if not els:
            return False
        mime = QMimeData()
        payload = json.dumps({"elements": [el.to_dict() for el in els]}, ensure_ascii=False)
        mime.setData(MIME, payload.encode("utf-8"))
        mime.setText(", ".join(_(el.name_key()) for el in els))
        QGuiApplication.clipboard().setMimeData(mime)
        return True

    def paste(self) -> bool:
        mime = QGuiApplication.clipboard().mimeData()
        if mime is None or not mime.hasFormat(MIME):
            return False
        try:
            items = json.loads(bytes(mime.data(MIME).data()).decode("utf-8")).get("elements", [])
        except (ValueError, AttributeError):
            return False
        step = max(self.doc.snap_step, 10.0) * 3
        return bool(self.paste_elements([i for i in items if isinstance(i, dict)], (step, step)))

    @staticmethod
    def can_paste() -> bool:
        mime = QGuiApplication.clipboard().mimeData()
        return mime is not None and mime.hasFormat(MIME)

    def rotate_selection(self) -> None:
        els = self.selected_elements()
        if not els:
            return
        c = selection_center(els)
        for el in els:
            el.rotate90(c)
        self.changed.emit("rotate")
        self.update()

    def bring_front(self) -> None:
        if self.selection:
            self.doc.bring_front(self.selection)
            self.changed.emit("order")
            self.update()

    def send_back(self) -> None:
        if self.selection:
            self.doc.send_back(self.selection)
            self.changed.emit("order")
            self.update()

    def select_all(self) -> None:
        self.set_selection([el.id for el in self.doc.elements])

    # ------------------------------------------------------------------------------ pintura
    def paintEvent(self, e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(self.rect(), QColor(t.canvas))
        if self.show_grid:
            self._paint_grid(p, t)
        style = render.Style(QColor(t.ink), QColor(t.canvas), min_pen=1.0 / self.scale)
        p.save()
        p.translate(self.ox, self.oy)
        p.scale(self.scale, self.scale)
        render.paint_document(p, self.doc, style)
        sel = self.selected_elements()
        for el in sel:
            if isinstance(el, Segment) and el.length() > 1e-6:
                halo = theme.qcolor(t.accent, 0.35)
                pen = QPen(halo, el.width + 9 / self.scale)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(*el.p1), QPointF(*el.p2))
        if self._hover_id and self.tool == "erase":
            el = self.doc.get(self._hover_id)
            if el is not None:
                render.paint_element(p, el, self.doc, style, QColor(t.danger))
        if self._preview is not None:
            render.paint_element(p, self._preview, self.doc, style, theme.qcolor(t.accent, 0.85))
        p.restore()
        self._paint_selection_boxes(p, t, sel)
        if len(sel) == 1 and self.tool == "select":
            self._paint_handles(p, t, sel[0])
        self._paint_snap(p, t)
        d = self._drag
        if d is not None and d.mode == "rubber":
            r = QRectF(d.press, d.cur).normalized()
            p.setPen(QPen(QColor(t.accent), 1))
            p.setBrush(theme.qcolor(t.accent, 0.08))
            p.drawRect(r)
        self._paint_measure(p, t)
        if not self.doc.elements and self._preview is None and self._draw_start is None and not self._poly_pts:
            self._paint_empty(p, t)
        p.end()

    def _paint_grid(self, p: QPainter, t: theme.Palette) -> None:
        s = self.scale
        minor = next((m for m in (1, 5, 10, 50, 100, 500, 1000) if m * s >= 10), 1000)
        major = next((m for m in (10, 50, 100, 500, 1000, 5000, 10000) if m * s >= 48 and m % minor == 0 and m > minor),
                     10000)
        x0, y0 = self.to_world(QPointF(0, 0))
        x1, y1 = self.to_world(QPointF(self.width(), self.height()))
        for step, color in ((minor, t.grid_minor), (major, t.grid_major)):
            if step == minor and minor * s < 10:
                continue
            p.setPen(QPen(QColor(color), 1))
            i = math.floor(x0 / step)
            while i * step <= x1:
                if step == major or (i * step) % major:
                    x = round(i * step * s + self.ox) + 0.5
                    p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
                i += 1
            j = math.floor(y0 / step)
            while j * step <= y1:
                if step == major or (j * step) % major:
                    y = round(j * step * s + self.oy) + 0.5
                    p.drawLine(QPointF(0, y), QPointF(self.width(), y))
                j += 1

    def _screen_rect(self, r: QRectF) -> QRectF:
        a = self.to_screen((r.left(), r.top()))
        b = self.to_screen((r.right(), r.bottom()))
        return QRectF(a, b).normalized()

    def _paint_selection_boxes(self, p: QPainter, t: theme.Palette, sel: list[Element]) -> None:
        ids = list(self._rubber_ids)
        targets = [el for el in sel if not isinstance(el, Segment)] + \
            [el for el in (self.doc.get(i) for i in ids) if el is not None and el.id not in self.selection]
        pen = QPen(QColor(t.accent), 1.4)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for el in targets:
            p.setPen(pen)
            p.drawRoundedRect(self._screen_rect(render.element_bounds(el, self.doc)).adjusted(-5, -5, 5, 5), 4, 4)
        for el in sel:
            box = render.label_box(el, self.doc)
            if box is not None:
                p.setPen(QPen(theme.qcolor(t.accent, 0.7), 1, Qt.PenStyle.DotLine))
                p.drawRect(self._screen_rect(box.rect()).adjusted(-3, -2, 3, 2))

    def _paint_handles(self, p: QPainter, t: theme.Palette, el: Element) -> None:
        for name, pt in render.handles(el, self.doc):
            q = self.to_screen(pt)
            r = QRectF(q.x() - 5.5, q.y() - 5.5, 11, 11)
            p.setPen(QPen(QColor(t.accent), 2))
            p.setBrush(QColor("#ffffff"))
            if name in ("p1", "p2", "offset"):
                p.drawEllipse(r)
            else:
                p.drawRoundedRect(r, 2.5, 2.5)

    def _paint_snap(self, p: QPainter, t: theme.Palette) -> None:
        if self._snap_mark is None or self.tool in ("select", "erase", "pan") and self._drag is None:
            return
        pt, kind = self._snap_mark
        q = self.to_screen(pt)
        p.setPen(QPen(QColor(t.accent), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if kind == "point":
            p.drawRect(QRectF(q.x() - 6, q.y() - 6, 12, 12))
        else:
            path = QPainterPath(QPointF(q.x(), q.y() - 7))
            path.lineTo(q.x() + 7, q.y())
            path.lineTo(q.x(), q.y() + 7)
            path.lineTo(q.x() - 7, q.y())
            path.closeSubpath()
            p.drawPath(path)

    def _measure_text(self) -> tuple[str, Point] | None:
        el = self._preview if self._draw_start is not None or self._poly_pts else None
        d = self._drag
        if el is None and d is not None and d.mode == "handle":
            el = self.doc.get(d.id)
        if el is None:
            return None
        if isinstance(el, (Segment, Dimension)):
            return render.fmt_len(el.length(), self.doc), el.p2
        if isinstance(el, Ellipse) and el.is_circle():
            return f"Ø {render.fmt_len(el.w, self.doc)}", (el.x + el.w, el.y + el.h)
        if isinstance(el, (Rect, Ellipse)):
            return f"{render.fmt_len(el.w, self.doc)} × {render.fmt_len(el.h, self.doc)}", (el.x + el.w, el.y + el.h)
        if isinstance(el, Polygon) and len(el.points) > 1:
            if self.tool == "triangle" and self._draw_start is not None:
                (x0, y1), (_xm, y0), (x1, _y) = el.pts()
                return f"{render.fmt_len(x1 - x0, self.doc)} × {render.fmt_len(y1 - y0, self.doc)}", (x1, y1)
            if self.tool == "poly" and self._poly_pts:
                a, b = el.pts()[-2], el.pts()[-1]
                return render.fmt_len(geo.dist(a, b), self.doc), b
        return None

    def _paint_measure(self, p: QPainter, t: theme.Palette) -> None:
        m = self._measure_text()
        if m is None:
            return
        text, at = m
        q = self.to_screen(at)
        f = QFont(self.font())
        f.setPointSizeF(10)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        fm = QFontMetricsF(f)
        w = fm.horizontalAdvance(text) + 18
        h = fm.height() + 8
        r = QRectF(q.x() + 14, q.y() + 14, w, h)
        if r.right() > self.width() - 4:
            r.moveRight(q.x() - 14)
        if r.bottom() > self.height() - 4:
            r.moveBottom(q.y() - 14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.accent))
        p.drawRoundedRect(r, h / 2, h / 2)
        p.setPen(QColor(t.on_accent))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_empty(self, p: QPainter, t: theme.Palette) -> None:
        f = QFont(self.font())
        f.setPointSizeF(11.5)
        p.setFont(f)
        p.setPen(QColor(t.faint))
        text = _("Folha em branco.\nEscolha uma ferramenta à esquerda (por exemplo, Viga)\n"
                 "e arraste aqui no quadriculado para desenhar.")
        r = QRectF(0, self.height() * 0.35, self.width(), self.height() * 0.3)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
