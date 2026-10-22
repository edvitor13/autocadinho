"""Painel da direita: ajustes do que está selecionado ou, sem seleção, do desenho e a dica da ferramenta.

Cada mudança feita aqui altera o documento e chama `MainWindow.commit(chave, source="panel")`.
O painel é refeito quando a seleção muda ou quando o desenho muda por outro caminho (mouse,
desfazer...); mudanças que vêm dele mesmo não o refazem, para não atrapalhar quem está digitando.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (QAbstractSpinBox, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFrame,
                               QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
                               QSpinBox, QToolButton, QVBoxLayout, QWidget)

from .. import geometry as geo
from .. import i18n, render
from ..i18n import N_, _
from ..model import Beam, Dimension, Element, Ellipse, Labeled, Line, Pillar, Polygon, Rect, Segment, Symbol, Text
from . import icons, theme

if TYPE_CHECKING:
    from .main_window import MainWindow

COLORS = [
    ("", N_("Automática (preto)")),
    ("#d64541", N_("Vermelho")),
    ("#2f6fdb", N_("Azul")),
    ("#2e9e5b", N_("Verde")),
    ("#e08a1e", N_("Laranja")),
    ("#8a6d4b", N_("Marrom")),
    ("#8a8f98", N_("Cinza")),
]

SNAP_STEPS = [(0.0, N_("Sem grade")), (1.0, "1 cm"), (5.0, "5 cm"), (10.0, "10 cm"), (25.0, "25 cm"),
              (50.0, "50 cm"), (100.0, "1 m")]

# Fontes comuns no Windows que aparecem primeiro na lista (só as que existirem no computador).
POPULAR_FONTS = ("Segoe UI", "Arial", "Calibri", "Verdana", "Tahoma", "Trebuchet MS", "Bahnschrift", "Times New Roman",
                 "Georgia", "Cambria", "Courier New", "Consolas", "Comic Sans MS", "Segoe Print", "Segoe Script",
                 "Ink Free", "Impact")


@lru_cache(maxsize=1)
def font_families() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(fontes comuns, todas as outras) instaladas que escrevem em português."""
    fams = [f for f in QFontDatabase.families(QFontDatabase.WritingSystem.Latin)
            if not f.startswith("@") and not QFontDatabase.isPrivateFamily(f)]
    popular = tuple(f for f in POPULAR_FONTS if f in fams)
    others = tuple(sorted((f for f in fams if f not in popular), key=str.casefold))
    return popular, others


TOOL_TIPS = {
    "select": ("select", N_("Selecionar e mover"),
               N_("Clique num desenho para escolher e arraste para mover. Arraste as bolinhas para mudar o tamanho. "
                  "Duplo clique muda um nome ou um texto. A tecla Delete apaga.")),
    "beam": ("beam", N_("Viga"),
             N_("Traço grosso com nome: vigas, paredes, muros. Clique onde começa e arraste até onde termina. "
                "Ele ganha um nome sozinho (VIGA 1, VIGA 2…). Depois, digite o comprimento exato aqui do lado.")),
    "line": ("line", N_("Linha"),
             N_("Para escadas, aberturas, paredes finas e detalhes. Clique e arraste. Ela pode ser tracejada.")),
    "pillar": ("pillar", N_("Pilar"),
               N_("Bloco cheio com nome: pilares, sapatas, caixas. Clique para colocar; ele encaixa nas pontas e no "
                  "meio das vigas. A tecla R deixa o bloco em pé ou deitado.")),
    "rect": ("rect", N_("Retângulo"),
             N_("Clique num canto e arraste até o canto oposto. Bom para lajes, aberturas e áreas.")),
    "ellipse": ("ellipse", N_("Círculo"),
                N_("Clique num canto e arraste até o canto oposto, como no Paint. Segure Shift para um círculo "
                   "perfeito. Bom para pilares redondos, caixas d'água e poços.")),
    "triangle": ("triangle", N_("Triângulo"),
                 N_("Clique num canto e arraste até o canto oposto. Depois, arraste as bolinhas para mudar cada "
                    "ponta.")),
    "poly": ("poly", N_("Polígono"),
             N_("Para terrenos e formas tortas: clique em cada canto, um depois do outro. Para terminar, clique no "
                "primeiro ponto, dê dois cliques ou aperte Enter. O painel mostra a área e o perímetro.")),
    "symbol": ("sym:door", N_("Símbolos"),
               N_("Portas, janelas, escada, louças e o norte. Escolha o símbolo no botão da esquerda e clique na "
                  "folha. Portas e janelas encaixam em cima de uma viga ou linha, abrem o vão na parede e seguem a "
                  "direção dela. A tecla R gira (ou vira o lado da porta).")),
    "dim": ("dim", N_("Medida"),
            N_("Clique e arraste do começo ao fim do que quer medir: a medida é calculada sozinha. "
               "Depois, arraste a bolinha do meio para afastar a linha da medida.")),
    "text": ("text", N_("Texto"),
             N_("Clique onde o texto vai ficar, escreva e aperte Enter.")),
    "erase": ("erase", N_("Borracha"),
              N_("Clique no que quer apagar, ou arraste por cima de vários. Errou? Ctrl+Z desfaz.")),
    "pan": ("pan", N_("Mover a folha"),
            N_("Arraste para ver outra parte do desenho. A rodinha do mouse aproxima e afasta.")),
}


class _Spin(QDoubleSpinBox):
    """Campo numérico que só reage à rodinha do mouse quando está em foco (não muda sem querer)."""

    def __init__(self) -> None:
        super().__init__()
        self.setKeyboardTracking(False)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lineEdit().setTextMargins(7, 0, 0, 0)  # o campo interno ignora o padding da folha de estilo

    def wheelEvent(self, e) -> None:  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class _Int(QSpinBox):
    """Campo de número inteiro que, como o _Spin, só reage à rodinha quando está em foco."""

    def __init__(self) -> None:
        super().__init__()
        self.setKeyboardTracking(False)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lineEdit().setTextMargins(7, 0, 0, 0)

    def wheelEvent(self, e) -> None:  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class _Combo(QComboBox):
    def wheelEvent(self, e) -> None:  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class _FontCombo(_Combo):
    """Escolha da fonte, cada nome escrito na própria fonte. A lista (centenas) só é montada ao abrir."""

    def __init__(self, current: str, first_label: str) -> None:
        super().__init__()
        self.setMaxVisibleItems(16)
        self._first = first_label
        self._filled = False
        self.addItem(first_label, "")
        if current:
            self._add(current)
            self.setCurrentIndex(1)

    def _add(self, family: str) -> None:
        installed = any(family in group for group in font_families())
        self.addItem(family if installed else _("{fonte} (não instalada)").format(fonte=family), family)
        f = QFont(family)
        f.setPointSizeF(10.5)
        self.setItemData(self.count() - 1, f, Qt.ItemDataRole.FontRole)

    def fill(self) -> None:
        if self._filled:
            return
        self._filled = True
        current = self.currentData() or ""
        self.blockSignals(True)
        self.clear()
        self.addItem(self._first, "")
        popular, others = font_families()
        for group in (popular, others):
            if group:
                self.insertSeparator(self.count())
            for fam in group:
                self._add(fam)
        if current and self.findData(current) < 0:
            self._add(current)
        self.setCurrentIndex(max(self.findData(current), 0))
        self.blockSignals(False)

    def showPopup(self) -> None:  # noqa: N802
        self.fill()
        super().showPopup()


class PropertiesPanel(QScrollArea):
    def __init__(self, win: "MainWindow") -> None:
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedWidth(312)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._grid: QGridLayout | None = None
        self._row = 0
        self.rebuild()

    @property
    def doc(self):
        return self.win.canvas.doc

    # ------------------------------------------------------------------------------ montagem
    def rebuild(self) -> None:
        body = QWidget()
        body.setObjectName("Side")
        self._lay = QVBoxLayout(body)
        self._lay.setContentsMargins(18, 18, 18, 18)
        self._lay.setSpacing(12)
        sel = self.win.canvas.selected_elements()
        if not sel:
            self._build_tip()
            self._build_document()
        elif len(sel) == 1:
            self._build_element(sel[0])
        else:
            self._build_multi(sel)
        self._lay.addStretch(1)
        # setWidget() apagaria o antigo na hora; tirado antes, ele some depois (pode estar no meio de um clique).
        old = self.takeWidget()
        self.setWidget(body)
        if old is not None:
            old.deleteLater()

    def rebuild_later(self) -> None:
        QTimer.singleShot(0, self.rebuild)

    def focus_text(self) -> None:
        edit = self.findChild(QPlainTextEdit)
        if edit is not None:
            edit.setFocus()
            edit.selectAll()

    def _commit(self, key: str, rebuild: bool = False) -> None:
        self.win.commit(key, source="panel")
        if rebuild:
            self.rebuild_later()

    # -- peças
    def _header(self, icon_name: str, kicker: str, title: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)
        ic = QLabel()
        icons.bind(ic, icon_name, "accent", 22)
        row.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(0)
        k = QLabel(kicker.upper())
        k.setObjectName("Kicker")
        col.addWidget(k)
        t = QLabel(title)
        t.setObjectName("H2")
        t.setWordWrap(True)
        col.addWidget(t)
        row.addLayout(col, 1)
        self._lay.addLayout(row)

    def _section(self, title: str | None = None) -> None:
        sep = QFrame()
        sep.setObjectName("HSep")
        self._lay.addWidget(sep)
        if title:
            k = QLabel(title.upper())
            k.setObjectName("Kicker")
            self._lay.addWidget(k)
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(9)
        self._grid.setColumnStretch(1, 1)
        self._row = 0
        self._lay.addLayout(self._grid)

    def _field(self, label: str, widget: QWidget) -> QWidget:
        if self._grid is None:
            self._section()
        lab = QLabel(label)
        lab.setObjectName("FieldLabel")
        self._grid.addWidget(lab, self._row, 0)
        self._grid.addWidget(widget, self._row, 1)
        self._row += 1
        return widget

    def _wide(self, widget: QWidget) -> QWidget:
        if self._grid is None:
            self._section()
        self._grid.addWidget(widget, self._row, 0, 1, 2)
        self._row += 1
        return widget

    def _length(self, cm: float, on_change: Callable[[float], None], minimum: float = 1.0) -> _Spin:
        sp = _Spin()
        if self.doc.unit == "m":
            sp.setDecimals(2)
            sp.setSuffix(" m")
            sp.setRange(minimum / 100, 99999)
            sp.setSingleStep(0.05)
            sp.setValue(cm / 100)
            sp.valueChanged.connect(lambda v: on_change(v * 100))
        else:
            sp.setDecimals(1)
            sp.setSuffix(" cm")
            sp.setRange(minimum, 9999999)
            sp.setSingleStep(5)
            sp.setValue(cm)
            sp.valueChanged.connect(on_change)
        return sp

    def _cm(self, value: float, lo: float, hi: float, on_change: Callable[[float], None], step: float = 1.0,
            decimals: int = 1) -> _Spin:
        sp = _Spin()
        sp.setDecimals(decimals)
        sp.setSuffix(" cm")
        sp.setRange(lo, hi)
        sp.setSingleStep(step)
        sp.setValue(value)
        sp.valueChanged.connect(on_change)
        return sp

    def _font(self, current: str, on_change: Callable[[str], None], first_label: str) -> _FontCombo:
        combo = _FontCombo(current, first_label)
        combo.currentIndexChanged.connect(lambda _i: on_change(combo.currentData() or ""))
        return combo

    def _info(self, label: str, text: str) -> None:
        value = QLabel(text)
        value.setObjectName("Value")
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._field(label, value)

    def _note(self, text: str) -> None:
        note = QLabel(text)
        note.setObjectName("Faint")
        note.setWordWrap(True)
        self._wide(note)

    def _check(self, text: str, value: bool, on_change: Callable[[bool], None]) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(value)
        cb.toggled.connect(on_change)
        return cb

    def _line_edit(self, value: str, on_change: Callable[[str], None], placeholder: str = "") -> QLineEdit:
        ed = QLineEdit(value)
        ed.setPlaceholderText(placeholder)
        ed.textEdited.connect(on_change)
        return ed

    def _colors(self, elements: list[Element]) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        group = QButtonGroup(box)
        group.setExclusive(True)
        current = elements[0].color if all(el.color == elements[0].color for el in elements) else None
        t = theme.current()
        swatches = list(COLORS)
        if current and current.lower() not in {v for v, _n in COLORS}:
            swatches.append((current, N_("Cor escolhida")))
        for value, name in swatches:
            b = QToolButton()
            b.setObjectName("Swatch")
            b.setCheckable(True)
            b.setToolTip(_(name))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            fill = value or t.ink
            b.setStyleSheet(f"QToolButton#Swatch {{ background: {fill}; }}")
            b.setChecked(value == current)
            b.clicked.connect(lambda _c=False, v=value: self._set_color(elements, v))
            group.addButton(b)
            row.addWidget(b)
        more = QToolButton()
        more.setObjectName("Swatch")
        icons.bind(more, "plus", "muted", 14)
        more.setToolTip(_("Outra cor…"))
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.clicked.connect(lambda: self._pick_color(elements, current))
        row.addWidget(more)
        row.addStretch(1)
        return box

    def _pick_color(self, elements: list[Element], current: str | None) -> None:
        start = QColor(current) if current else QColor(theme.current().ink)
        color = QColorDialog.getColor(start, self, _("Escolher a cor"))
        if color.isValid():
            self._set_color(elements, color.name())
            self.rebuild_later()

    def _set_color(self, elements: list[Element], value: str) -> None:
        for el in elements:
            el.color = value
        self._commit("color")

    def _buttons(self, elements: list[Element]) -> None:
        sep = QFrame()
        sep.setObjectName("HSep")
        self._lay.addWidget(sep)
        row = QHBoxLayout()
        row.setSpacing(8)
        rot = QPushButton(_("Girar"))
        icons.bind(rot, "rotate", "text", 18)
        rot.setToolTip(_("Girar 90° (R)"))
        rot.clicked.connect(self.win.canvas.rotate_selection)
        dup = QPushButton(_("Duplicar"))
        icons.bind(dup, "duplicate", "text", 18)
        dup.setToolTip(_("Duplicar (Ctrl+D)"))
        dup.clicked.connect(self.win.canvas.duplicate_selection)
        row.addWidget(rot)
        row.addWidget(dup)
        self._lay.addLayout(row)
        dele = QPushButton(_("Apagar"))
        dele.setObjectName("Danger")
        icons.bind(dele, "trash", "danger", 18)
        dele.setToolTip(_("Apagar (Delete)"))
        dele.clicked.connect(self.win.canvas.delete_selection)
        self._lay.addWidget(dele)

    # ------------------------------------------------------------------------------ sem seleção
    def _build_tip(self) -> None:
        icon_name, title, text = TOOL_TIPS.get(self.win.canvas.tool, TOOL_TIPS["select"])
        card = QFrame()
        card.setObjectName("TipCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        ic = QLabel()
        icons.bind(ic, icon_name, "accent", 20)
        head.addWidget(ic)
        t = QLabel(_(title))
        t.setObjectName("TipTitle")
        head.addWidget(t, 1)
        lay.addLayout(head)
        body = QLabel(_(text))
        body.setObjectName("TipText")
        body.setWordWrap(True)
        lay.addWidget(body)
        self._lay.addWidget(card)

    def _build_document(self) -> None:
        doc = self.doc
        self._section(_("Desenho"))
        self._field(_("Título"), self._line_edit(doc.title, self._set_title, _("Ex.: Mezanino da loja")))
        unit = _Combo()
        unit.addItem(_("metros ({exemplo})").format(exemplo=geo.format_length(350, "m", i18n.decimal_sep())), "m")
        unit.addItem(_("centímetros ({exemplo})").format(exemplo="350 cm"), "cm")
        unit.setCurrentIndex(0 if doc.unit == "m" else 1)
        unit.currentIndexChanged.connect(lambda _i: self._set_doc("unit", unit.currentData(), rebuild=True))
        self._field(_("Medidas em"), unit)
        snap = _Combo()
        for value, name in SNAP_STEPS:
            snap.addItem(_(name), value)
        idx = next((i for i, (v, _n) in enumerate(SNAP_STEPS) if abs(v - doc.snap_step) < 1e-6), -1)
        if idx < 0:
            snap.addItem(f"{doc.snap_step:g} cm", doc.snap_step)
            idx = snap.count() - 1
        snap.setCurrentIndex(idx)
        snap.currentIndexChanged.connect(lambda _i: self._set_doc("snap_step", float(snap.currentData())))
        snap.setToolTip(_("Os desenhos encaixam nos pontos da grade, de tantos em tantos centímetros."))
        self._field(_("Encaixe"), snap)

        self._section(_("Nomes automáticos"))
        self._field(_("Vigas"), self._line_edit(doc.beam_prefix, lambda v: self._set_prefix("beam_prefix", v),
                                                _("sem nome")))
        self._field(_("Pilares"), self._line_edit(doc.pillar_prefix, lambda v: self._set_prefix("pillar_prefix", v),
                                                  _("sem nome")))
        note = QLabel(_("Cada viga ou pilar novo ganha o próximo número (VIGA 1, VIGA 2… ou P1, P2…). "
                        "Troque a palavra (PAREDE, SAPATA…) ou deixe vazio para desenhar sem nome."))
        note.setObjectName("Faint")
        note.setWordWrap(True)
        self._wide(note)

        self._section(_("Tamanhos"))
        self._field(_("Letras"), self._cm(doc.label_size, 2, 500, lambda v: self._set_doc("label_size", v), 1, 1))
        self._field(_("Fonte"), self._font(doc.font, lambda v: self._set_doc("font", v),
                                           _("Padrão ({fonte})").format(fonte=render.font_family())))
        self._field(_("Vigas novas"), self._cm(doc.beam_width, 1, 200, lambda v: self._set_doc("beam_width", v), 1, 1))
        size = QWidget()
        row = QHBoxLayout(size)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self._cm(doc.pillar_w, 1, 500, lambda v: self._set_doc("pillar_w", v), 5, 0))
        x = QLabel("×")
        x.setObjectName("Muted")
        row.addWidget(x)
        row.addWidget(self._cm(doc.pillar_h, 1, 500, lambda v: self._set_doc("pillar_h", v), 5, 0))
        self._field(_("Pilares novos"), size)
        self._note(_("O tamanho das letras vale para os nomes e as medidas. A fonte vale também para os textos "
                     "que usam a mesma do desenho."))

        counts = [(doc.count("beam"), _("viga"), _("vigas")), (doc.count("pillar"), _("pilar"), _("pilares")),
                  (doc.count("dim"), _("medida"), _("medidas")), (doc.count("symbol"), _("símbolo"), _("símbolos"))]
        parts = [f"{n} {one if n == 1 else many}" for n, one, many in counts if n]
        if parts:
            info = QLabel(" · ".join(parts))
            info.setObjectName("Faint")
            self._lay.addWidget(info)

    def _set_title(self, text: str) -> None:
        self.doc.title = text
        self._commit("title")

    def _set_prefix(self, key: str, text: str) -> None:
        setattr(self.doc, key, text.strip()[:self.doc.PREFIX_MAX])
        self._commit(f"doc:{key}")

    def _set_doc(self, key: str, value, rebuild: bool = False) -> None:
        setattr(self.doc, key, value)
        self._commit(f"doc:{key}", rebuild)

    # ------------------------------------------------------------------------------ um elemento
    def _build_element(self, el: Element) -> None:
        kind_name = _(el.name_key())
        name = el.label if isinstance(el, Labeled) and el.label else kind_name
        icon_name = {"beam": "beam", "line": "line", "pillar": "pillar", "rect": "rect", "text": "text",
                     "dim": "dim", "ellipse": "ellipse", "poly": "poly"}.get(el.kind, "select")
        if isinstance(el, Polygon) and el.closed and len(el.points) == 3:
            icon_name = "triangle"
        elif isinstance(el, Symbol):
            icon_name = f"sym:{el.shape}"
        self._header(icon_name, kind_name, name)
        if isinstance(el, Labeled):
            self._section(_("Nome"))
            self._wide(self._line_edit(el.label, lambda v: self._set(el, "label", v, "label"), _("Sem nome")))
            self._wide(self._check(_("Mostrar o nome"), el.label_visible,
                                   lambda v: self._set(el, "label_visible", v, "label_visible")))
            self._wide(self._check(_("Nome em pé"), bool(el.label_rot),
                                   lambda v: self._set(el, "label_rot", 90 if v else 0, "label_rot")))
            if el.label_dx is not None:
                reset = QPushButton(_("Voltar o nome para o lugar automático"))
                reset.setObjectName("Flat")
                reset.clicked.connect(lambda: self._reset_label(el))
                self._wide(reset)
        if isinstance(el, Segment):
            self._section(_("Medidas"))
            self._field(_("Comprimento"), self._length(el.length(), lambda v: self._set_length(el, v)))
            if isinstance(el, Beam):
                self._field(_("Largura"), self._cm(el.width, 1, 200, lambda v: self._set(el, "width", v, "width")))
            else:
                self._field(_("Espessura"), self._cm(el.width, 0.1, 100, lambda v: self._set(el, "width", v, "width"),
                                                      0.5, 1))
                self._wide(self._check(_("Tracejada"), el.dashed, lambda v: self._set(el, "dashed", v, "dashed")))
            if isinstance(el, Line):
                self._wide(self._check(_("Seta no começo"), el.arrow_start,
                                       lambda v: self._set(el, "arrow_start", v, "arrow_start")))
                self._wide(self._check(_("Seta no fim"), el.arrow_end,
                                       lambda v: self._set(el, "arrow_end", v, "arrow_end")))
            self._wide(self._check(_("Escrever a medida ao lado"), el.show_length,
                                   lambda v: self._set(el, "show_length", v, "show_length")))
        elif isinstance(el, Pillar):
            self._section(_("Medidas"))
            self._field(_("Largura"), self._cm(el.w, 1, 500, lambda v: self._set(el, "w", v, "w"), 5, 0))
            self._field(_("Comprimento"), self._cm(el.h, 1, 500, lambda v: self._set(el, "h", v, "h"), 5, 0))
            turn = QPushButton(_("Deixar em pé / deitado"))
            icons.bind(turn, "rotate", "text", 18)
            turn.clicked.connect(lambda: self._turn(el))
            self._wide(turn)
        elif isinstance(el, Rect):
            self._section(_("Medidas"))
            self._field(_("Largura"), self._length(el.w, lambda v: self._set(el, "w", v, "w")))
            self._field(_("Altura"), self._length(el.h, lambda v: self._set(el, "h", v, "h")))
            self._field(_("Espessura"), self._cm(el.width, 0.1, 100, lambda v: self._set(el, "width", v, "width"), 0.5, 1))
            self._wide(self._check(_("Tracejado"), el.dashed, lambda v: self._set(el, "dashed", v, "dashed")))
            self._wide(self._check(_("Preenchido"), el.fill, lambda v: self._set(el, "fill", v, "fill")))
            self._wide(self._check(_("Escrever as medidas"), el.show_dims,
                                   lambda v: self._set(el, "show_dims", v, "show_dims")))
            self._area_rows(el, el.w * el.h)
        elif isinstance(el, Ellipse):
            self._section(_("Medidas"))
            circle = el.is_circle()
            self._wide(self._check(_("Círculo perfeito"), circle, lambda v: self._set_circle(el, v)))
            if circle:
                self._field(_("Diâmetro"), self._length(el.w, lambda v: self._set_diameter(el, v)))
            else:
                self._field(_("Largura"), self._length(el.w, lambda v: self._set(el, "w", v, "w")))
                self._field(_("Altura"), self._length(el.h, lambda v: self._set(el, "h", v, "h")))
            self._field(_("Espessura"), self._cm(el.width, 0.1, 100, lambda v: self._set(el, "width", v, "width"), 0.5, 1))
            self._wide(self._check(_("Tracejado"), el.dashed, lambda v: self._set(el, "dashed", v, "dashed")))
            self._wide(self._check(_("Preenchido"), el.fill, lambda v: self._set(el, "fill", v, "fill")))
            self._wide(self._check(_("Escrever as medidas"), el.show_dims,
                                   lambda v: self._set(el, "show_dims", v, "show_dims")))
            self._area_rows(el, el.area())
        elif isinstance(el, Polygon):
            self._section(_("Medidas"))
            self._info(_("Pontos"), str(len(el.points)))
            self._info(_("Perímetro"), render.fmt_len(el.perimeter(), self.doc))
            self._field(_("Espessura"), self._cm(el.width, 0.1, 100, lambda v: self._set(el, "width", v, "width"), 0.5, 1))
            self._wide(self._check(_("Fechar a forma"), el.closed,
                                   lambda v: self._set(el, "closed", v, "closed", rebuild=True)))
            self._wide(self._check(_("Tracejado"), el.dashed, lambda v: self._set(el, "dashed", v, "dashed")))
            if el.closed:
                self._wide(self._check(_("Preenchido"), el.fill, lambda v: self._set(el, "fill", v, "fill")))
            self._wide(self._check(_("Escrever a medida dos lados"), el.show_lengths,
                                   lambda v: self._set(el, "show_lengths", v, "show_lengths")))
            if el.closed:
                self._area_rows(el, el.area())
            self._note(_("Arraste as bolinhas para mudar cada ponta."))
        elif isinstance(el, Symbol):
            self._build_symbol(el)
        elif isinstance(el, Text):
            self._section(_("Texto"))
            edit = QPlainTextEdit(el.text)
            edit.setFixedHeight(84)
            edit.textChanged.connect(lambda: self._set(el, "text", edit.toPlainText(), "text"))
            self._wide(edit)
            self._field(_("Letras"), self._cm(el.size, 2, 1000, lambda v: self._set(el, "size", v, "size"), 1, 1))
            self._field(_("Fonte"), self._font(el.font, lambda v: self._set(el, "font", v, "font"),
                                               _("A mesma do desenho")))
            self._wide(self._check(_("Negrito"), el.bold, lambda v: self._set(el, "bold", v, "bold")))
            self._wide(self._check(_("Itálico"), el.italic, lambda v: self._set(el, "italic", v, "italic")))
            self._wide(self._check(_("Texto em pé"), bool(el.rot), lambda v: self._set(el, "rot", 90 if v else 0, "rot")))
        elif isinstance(el, Dimension):
            self._section(_("Medida"))
            value = QLabel(render.fmt_len(el.length(), self.doc))
            value.setObjectName("H2")
            self._field(_("Distância"), value)
            self._field(_("Escrever"), self._line_edit(el.text, lambda v: self._set(el, "text", v.strip(), "text"),
                                                       _("a medida certa")))
            self._field(_("Afastamento"), self._cm(el.offset, -100000, 100000,
                                                   lambda v: self._set(el, "offset", v, "offset"), 5, 0))
            note = QLabel(_("Deixe \"Escrever\" vazio para mostrar a medida calculada."))
            note.setObjectName("Faint")
            note.setWordWrap(True)
            self._wide(note)
        self._section(_("Cor"))
        self._wide(self._colors([el]))
        self._buttons([el])

    def _area_rows(self, el: Rect | Ellipse | Polygon, area: float) -> None:
        self._wide(self._check(_("Escrever a área"), el.show_area,
                               lambda v: self._set(el, "show_area", v, "show_area")))
        self._info(_("Área"), geo.format_area(area, i18n.decimal_sep()))

    def _build_symbol(self, el: Symbol) -> None:
        self._section(_("Medidas"))
        if el.in_wall():
            self._field(_("Largura do vão"), self._length(el.w, lambda v: self._set(el, "w", v, "w")))
            self._field(_("Parede"), self._cm(el.wall, 0, 200, lambda v: self._set(el, "wall", v, "wall"), 1, 1))
            self._note(_("Com a espessura da parede, o símbolo abre o vão na viga ou linha de baixo. Com 0, não abre."))
            if el.shape == "door":
                self._wide(self._check(_("Dobradiça do outro lado"), el.flip_x,
                                       lambda v: self._set(el, "flip_x", v, "flip_x")))
            if el.shape in ("door", "door2"):
                self._wide(self._check(_("Abre para o outro lado"), el.flip_y,
                                       lambda v: self._set(el, "flip_y", v, "flip_y")))
            if el.shape == "sliding":
                self._wide(self._check(_("Espelhar"), el.flip_x, lambda v: self._set(el, "flip_x", v, "flip_x")))
        elif el.shape == "north":
            self._field(_("Tamanho"), self._cm(el.w, 10, 5000, lambda v: self._set_size(el, v), 5, 0))
        elif el.shape == "stairs":
            self._field(_("Comprimento"), self._length(el.w, lambda v: self._set(el, "w", v, "w", rebuild=True)))
            self._field(_("Largura"), self._length(el.h, lambda v: self._set(el, "h", v, "h")))
            steps = _Int()
            steps.setRange(0, 200)
            steps.setSpecialValueText(_("automático ({n})").format(n=el.step_count()))
            steps.setValue(el.steps)
            steps.valueChanged.connect(lambda v: self._set(el, "steps", v, "steps"))
            self._field(_("Degraus"), steps)
            self._wide(self._check(_("Inverter o sentido"), el.flip_x, lambda v: self._set(el, "flip_x", v, "flip_x")))
        else:
            self._field(_("Largura"), self._length(el.w, lambda v: self._set(el, "w", v, "w")))
            self._field(_("Comprimento"), self._length(el.h, lambda v: self._set(el, "h", v, "h")))

    def _set(self, el: Element, key: str, value, commit_key: str, rebuild: bool = False) -> None:
        setattr(el, key, value)
        self._commit(f"{commit_key}:{el.id}", rebuild)

    def _set_circle(self, el: Ellipse, on: bool) -> None:
        cx, cy = el.center()
        if on:
            el.h = el.w
        else:
            el.h = el.w * 0.6
        el.y = cy - el.h / 2
        el.x = cx - el.w / 2
        self._commit(f"circle:{el.id}", rebuild=True)

    def _set_diameter(self, el: Ellipse, d: float) -> None:
        cx, cy = el.center()
        el.w = el.h = d
        el.x, el.y = cx - d / 2, cy - d / 2
        self._commit(f"diameter:{el.id}")

    def _set_size(self, el: Symbol, size: float) -> None:
        el.w = el.h = size
        self._commit(f"size:{el.id}")

    def _set_length(self, el: Segment, cm: float) -> None:
        el.set_length(cm)
        self._commit(f"length:{el.id}")

    def _reset_label(self, el: Labeled) -> None:
        el.label_dx = el.label_dy = None
        self._commit("label-reset", rebuild=True)

    def _turn(self, el: Pillar) -> None:
        el.turn()
        self._commit("turn", rebuild=True)

    # ------------------------------------------------------------------------------ vários
    def _build_multi(self, sel: list[Element]) -> None:
        self._header("select", _("Seleção"), _("{n} itens selecionados").format(n=len(sel)))
        segs = [el for el in sel if isinstance(el, Segment)]
        if segs:
            self._section(_("Medidas"))
            self._wide(self._check(_("Escrever a medida ao lado"), all(s.show_length for s in segs),
                                   lambda v: self._set_many(segs, "show_length", v)))
        labeled = [el for el in sel if isinstance(el, Labeled)]
        if labeled:
            self._section(_("Nome"))
            self._wide(self._check(_("Mostrar os nomes"), all(el.label_visible for el in labeled),
                                   lambda v: self._set_many(labeled, "label_visible", v)))
        self._section(_("Cor"))
        self._wide(self._colors(sel))
        self._buttons(sel)

    def _set_many(self, elements: list[Element], key: str, value) -> None:
        for el in elements:
            setattr(el, key, value)
        self._commit(f"many:{key}")
