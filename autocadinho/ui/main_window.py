"""Janela principal: tela inicial, barra de cima, ferramentas, área de desenho, painel e barra de status.

Guarda o estado do desenho aberto (caminho, histórico, salvo ou não) e é o único lugar que grava
passos no histórico (`commit`). A área de desenho e o painel mudam o documento e avisam.
A troca de idioma remonta a interface inteira (`_build`) sem perder o desenho aberto.
"""

from __future__ import annotations

import json
import os
import re
import sys

from PySide6.QtCore import QDateTime, QLocale, QPoint, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMenu,
                               QMessageBox, QSizePolicy, QStackedWidget, QStatusBar, QToolButton, QVBoxLayout,
                               QWidget)

from .. import APP_NAME, FILE_EXT, REPO_URL, __date__, __version__, fileio, i18n, printing, render, samples
from ..history import History
from ..i18n import N_, _
from ..model import Document
from . import icons, prefs, theme
from .canvas import Canvas
from .home import HomePage
from .properties import PropertiesPanel

# (ferramenta, nome no botão, tecla de atalho). As teclas não mudam com o idioma.
TOOLS = [
    ("select", N_("Selecionar"), "S"),
    ("beam", N_("Viga"), "V"),
    ("pillar", N_("Pilar"), "P"),
    ("line", N_("Linha"), "L"),
    ("rect", N_("Retângulo"), "Q"),
    ("dim", N_("Medida"), "M"),
    ("text", N_("Texto"), "T"),
    ("erase", N_("Borracha"), "E"),
    ("pan", N_("Mover\nfolha"), "H"),
]
TOOL_GROUPS_AFTER = {"select", "rect", "text"}  # linha separadora depois destes
RECOVERY_DELAY_MS = 4000
MERGE_FROM_CANVAS = {"nudge"}  # passos da área de desenho que se juntam quando seguidos (setas do teclado)


def _clean_name(text: str) -> str:
    """Nome de arquivo a partir do título do desenho (sem caracteres proibidos no Windows)."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text).strip(" .")
    return re.sub(r"\s+", " ", name)[:80]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.path: str | None = None
        self.history = History()
        self._saved_state: str | None = None
        self._has_doc = False
        self._actions: dict[str, QAction] = {}
        self._recovery_timer = QTimer(self)
        self._recovery_timer.setSingleShot(True)
        self._recovery_timer.setInterval(RECOVERY_DELAY_MS)
        self._recovery_timer.timeout.connect(self._write_recovery)
        self.setWindowIcon(icons.app_icon())
        self.setAcceptDrops(True)
        self.setMinimumSize(980, 620)
        self.resize(1360, 860)
        self._build()
        geo = prefs.settings().value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        self._apply_titlebar()

    # ------------------------------------------------------------------------------ montagem
    def _build(self) -> None:
        """Monta (ou remonta, na troca de idioma) toda a interface, mantendo o desenho aberto."""
        old = getattr(self, "canvas", None)
        for act in self._actions.values():
            self.removeAction(act)
            act.deleteLater()
        self._actions = {}
        self.canvas = Canvas()
        if old is not None:
            self.canvas.show_grid, self.canvas.snap_on, self.canvas.ortho_on = old.show_grid, old.snap_on, old.ortho_on
            self.canvas.set_document(old.doc, fit=False)
            self.canvas.set_view_state(old.view_state())
            self.canvas.set_selection(old.selection)
        else:
            self.canvas.show_grid = prefs.get_bool("grid", True)
            self.canvas.snap_on = prefs.get_bool("snap", True)
            self.canvas.ortho_on = prefs.get_bool("ortho", True)
        self.panel = PropertiesPanel(self)
        self.home = HomePage()
        self.home.newRequested.connect(self.new_document)
        self.home.openRequested.connect(self.open_dialog)
        self.home.exampleRequested.connect(self.open_example)
        self.home.backRequested.connect(self.show_editor)
        self.home.recentRequested.connect(self.open_path)

        editor = QWidget()
        col = QVBoxLayout(editor)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._top_bar())
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._tool_rail())
        row.addWidget(self._canvas_area(), 1)
        row.addWidget(self.panel)
        col.addLayout(row, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.home)
        self.stack.addWidget(editor)
        self.stack.currentChanged.connect(lambda _i: self._refresh())
        self.setCentralWidget(self.stack)
        self._build_status()
        self._build_actions()

        c = self.canvas
        c.changed.connect(lambda key: self.commit(key, source="canvas"))
        c.selectionChanged.connect(self._on_selection)
        c.toolChanged.connect(self._on_tool)
        c.hintChanged.connect(self.hint_label.setText)
        c.cursorMoved.connect(self._on_cursor)
        c.viewChanged.connect(self._on_view)
        c.contextRequested.connect(self._context_menu)
        c.editRequested.connect(lambda _id: self.panel.focus_text())
        c.set_tool(old.tool if old is not None else "select")
        self._on_view()
        self._update_theme_button()
        self._refresh()

    def _flat(self, text: str, icon_name: str, slot, tip: str = "", primary: bool = False) -> QToolButton:
        b = QToolButton()
        b.setObjectName("Primary" if primary else "Flat")
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text else Qt.ToolButtonStyle.ToolButtonIconOnly)
        icons.bind(b, icon_name, "on_accent" if primary else "text", 20)
        b.setToolTip(tip or text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    @staticmethod
    def _vsep() -> QFrame:
        sep = QFrame()
        sep.setObjectName("Sep")
        sep.setFixedHeight(26)
        return sep

    def _top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(60)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 12, 8)
        row.setSpacing(4)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(32))
        row.addWidget(logo)
        row.addSpacing(8)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.title_label = QLabel()
        self.title_label.setObjectName("AppTitle")
        self.file_label = QLabel()
        self.file_label.setObjectName("DocTitle")
        names.addWidget(self.title_label)
        names.addWidget(self.file_label)
        row.addLayout(names)
        row.addSpacing(18)
        row.addWidget(self._vsep())
        row.addSpacing(4)
        row.addWidget(self._flat(_("Início"), "home", self.show_home, _("Voltar à tela inicial")))
        row.addWidget(self._flat(_("Novo"), "new", self.new_document, _("Começar um desenho novo (Ctrl+N)")))
        row.addWidget(self._flat(_("Abrir"), "open", self.open_dialog, _("Abrir um desenho salvo (Ctrl+O)")))
        self.save_btn = self._flat(_("Salvar"), "save", self.save, _("Salvar o desenho (Ctrl+S)"))
        row.addWidget(self.save_btn)
        row.addSpacing(4)
        row.addWidget(self._vsep())
        row.addSpacing(4)
        self.undo_btn = self._flat("", "undo", self.undo, _("Desfazer (Ctrl+Z)"))
        self.redo_btn = self._flat("", "redo", self.redo, _("Refazer (Ctrl+Y)"))
        row.addWidget(self.undo_btn)
        row.addWidget(self.redo_btn)
        row.addStretch(1)
        row.addWidget(self._flat(_("Imprimir"), "print", self.print_dialog,
                                 _("Imprimir ou salvar em PDF, com escala (Ctrl+P)"), primary=True))
        row.addSpacing(8)
        self.theme_btn = self._flat("", "moon", self.toggle_theme)
        row.addWidget(self.theme_btn)
        more = QToolButton()
        more.setObjectName("Flat")
        icons.bind(more, "more", "text", 20)
        more.setToolTip(_("Mais opções"))
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        menu.aboutToShow.connect(lambda: self._fill_more_menu(menu))
        more.setMenu(menu)
        row.addWidget(more)
        return bar

    def _fill_more_menu(self, menu: QMenu) -> None:
        """Monta o menu "mais opções" na hora de abrir (ícones nas cores do tema atual)."""
        menu.clear()
        menu.addAction(icons.icon("save"), _("Salvar como…"), self.save_as).setEnabled(self._has_doc)
        menu.addAction(icons.icon("pdf"), _("Salvar em PDF…"), self.export_pdf).setEnabled(self._has_doc)
        menu.addAction(icons.icon("image"), _("Salvar como imagem…"), self.export_png).setEnabled(self._has_doc)
        menu.addSeparator()
        lang = menu.addMenu(icons.icon("globe"), _("Idioma"))
        for code, name in i18n.LANGUAGES.items():
            act = lang.addAction(name, lambda c=code: self.set_language(c))
            act.setCheckable(True)
            act.setChecked(code == i18n.language())
        look = menu.addMenu(icons.icon("sun"), _("Tema"))
        for name, label in theme.THEME_LABELS.items():
            act = look.addAction(_(label), lambda n=name: self.set_theme(n))
            act.setCheckable(True)
            act.setChecked(name == theme.current().name)
        menu.addSeparator()
        menu.addAction(icons.icon("plan"), _("Abrir o desenho de exemplo"), self.open_example)
        menu.addAction(icons.icon("help"), _("Como usar") + "	F1", self.show_help)
        menu.addAction(icons.icon("info"), _("Sobre o Autocadinho"), self.show_about)

    def _tool_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("ToolRail")
        rail.setFixedWidth(88)
        col = QVBoxLayout(rail)
        col.setContentsMargins(8, 10, 8, 10)
        col.setSpacing(3)
        self._tool_group = QButtonGroup(rail)
        self._tool_group.setExclusive(True)
        self._tool_buttons: dict[str, QToolButton] = {}
        for name, label, key in TOOLS:
            b = QToolButton()
            b.setObjectName("Tool")
            b.setCheckable(True)
            b.setText(_(label))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            icons.bind(b, name, "muted", 22, on_role="accent")
            b.setToolTip(f"{_(label).replace(chr(10), ' ')} ({key})")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(58)
            # O QToolButton tem largura fixa pelo texto; aqui todos ocupam a coluna inteira, com o ícone no meio.
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _c=False, n=name: self.canvas.set_tool(n))
            self._tool_group.addButton(b)
            self._tool_buttons[name] = b
            col.addWidget(b)
            if name in TOOL_GROUPS_AFTER:
                sep = QFrame()
                sep.setObjectName("HSep")
                col.addSpacing(3)
                col.addWidget(sep)
                col.addSpacing(3)
        col.addStretch(1)
        return rail

    def _canvas_area(self) -> QWidget:
        area = QWidget()
        grid = QGridLayout(area)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self.canvas, 0, 0)
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 16, 16)
        box = QWidget()
        box.setObjectName("ZoomBox")
        bl = QHBoxLayout(box)
        bl.setContentsMargins(4, 3, 4, 3)
        bl.setSpacing(0)
        bl.addWidget(self._zoom_btn("zoom_out", _("Afastar (Ctrl+-)"), lambda: self.canvas.zoom_at(1 / 1.25)))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("ZoomLabel")
        bl.addWidget(self.zoom_label)
        bl.addWidget(self._zoom_btn("zoom_in", _("Aproximar (Ctrl++)"), lambda: self.canvas.zoom_at(1.25)))
        bl.addWidget(self._zoom_btn("fit", _("Ver o desenho inteiro (Ctrl+0)"), self.canvas.fit))
        hl.addWidget(box)
        grid.addWidget(holder, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        return area

    @staticmethod
    def _zoom_btn(name: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        icons.bind(b, name, "muted", 18)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _toggle(self, text: str, icon_name: str, checked: bool, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setObjectName("Toggle")
        b.setCheckable(True)
        b.setChecked(checked)
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        icons.bind(b, icon_name, "muted", 16, on_role="accent")
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.toggled.connect(slot)
        return b

    def _build_status(self) -> None:
        bar = QStatusBar()
        bar.setSizeGripEnabled(False)
        self.setStatusBar(bar)
        self.hint_label = QLabel()
        bar.addWidget(self.hint_label, 1)
        c = self.canvas
        self.grid_btn = self._toggle(_("Grade"), "grid", c.show_grid, _("Mostrar o quadriculado"), self._set_grid)
        self.snap_btn = self._toggle(_("Encaixe"), "magnet", c.snap_on,
                                     _("Encaixar nas pontas, nos meios e na grade (segure Alt para soltar)"),
                                     self._set_snap)
        self.ortho_btn = self._toggle(_("Retas 90°"), "ortho", c.ortho_on,
                                      _("Vigas e linhas só na horizontal ou na vertical (segure Shift para inclinar)"),
                                      self._set_ortho)
        for b in (self.grid_btn, self.snap_btn, self.ortho_btn):
            bar.addPermanentWidget(b)
        self.coords_label = QLabel()
        self.coords_label.setObjectName("Coords")
        self.coords_label.setMinimumWidth(190)
        bar.addPermanentWidget(self.coords_label)

    def _action(self, key: str, text: str, slot, shortcuts=(), icon_name: str | None = None) -> QAction:
        act = QAction(text, self)
        if shortcuts:
            act.setShortcuts([QKeySequence(s) for s in shortcuts])
        if icon_name:
            act.setProperty("acIcon", icon_name)
            act.setIcon(icons.icon(icon_name))
        act.triggered.connect(slot)
        self.addAction(act)
        self._actions[key] = act
        return act

    def _build_actions(self) -> None:
        c = self.canvas
        self._action("new", _("Novo desenho"), self.new_document, ["Ctrl+N"])
        self._action("open", _("Abrir…"), self.open_dialog, ["Ctrl+O"])
        self._action("save", _("Salvar"), self.save, ["Ctrl+S"])
        self._action("save_as", _("Salvar como…"), self.save_as, ["Ctrl+Shift+S"])
        self._action("print", _("Imprimir…"), self.print_dialog, ["Ctrl+P"])
        self._action("undo", _("Desfazer"), self.undo, ["Ctrl+Z"], "undo")
        self._action("redo", _("Refazer"), self.redo, ["Ctrl+Y", "Ctrl+Shift+Z"], "redo")
        self._action("copy", _("Copiar"), c.copy_selection, ["Ctrl+C"])
        self._action("cut", _("Recortar"), self.cut, ["Ctrl+X"])
        self._action("paste", _("Colar"), c.paste, ["Ctrl+V"])
        self._action("duplicate", _("Duplicar"), c.duplicate_selection, ["Ctrl+D"], "duplicate")
        self._action("rotate", _("Girar 90°") + "\tR", c.rotate_selection, (), "rotate")
        self._action("front", _("Trazer para a frente"), c.bring_front, (), "front")
        self._action("back", _("Mandar para trás"), c.send_back, (), "back")
        self._action("delete", _("Apagar"), c.delete_selection, ["Del"], "trash")
        self._action("select_all", _("Selecionar tudo"), c.select_all, ["Ctrl+A"])
        self._action("fit", _("Ver o desenho inteiro"), c.fit, ["Ctrl+0"], "fit")
        self._action("zoom_in", _("Aproximar"), lambda: c.zoom_at(1.25), ["Ctrl++", "Ctrl+="])
        self._action("zoom_out", _("Afastar"), lambda: c.zoom_at(1 / 1.25), ["Ctrl+-"])
        self._action("help", _("Como usar"), self.show_help, ["F1"])
        for name, label, key in TOOLS:
            self._action(f"tool:{name}", _(label), lambda _c=False, n=name: c.set_tool(n), [key])

    # ------------------------------------------------------------------------------ estado
    def _state(self) -> str:
        return json.dumps(self.canvas.doc.to_dict(), ensure_ascii=False, sort_keys=True)

    def is_dirty(self) -> bool:
        return self._has_doc and self.history.current != self._saved_state

    def doc_name(self) -> str:
        title = self.canvas.doc.title.strip()
        if title:
            return title
        if self.path:
            return os.path.splitext(os.path.basename(self.path))[0]
        return _("Desenho sem título")

    def commit(self, key: str = "", source: str = "canvas") -> None:
        """Grava um passo no histórico depois de uma mudança no desenho."""
        merge = key if (source == "panel" or key in MERGE_FROM_CANVAS) else None
        if self.history.push(self._state(), merge):
            if self.is_dirty() and not self._recovery_timer.isActive():
                self._recovery_timer.start()
        self.canvas.update()
        if source != "panel":
            self.panel.rebuild()
        self._refresh()

    def _refresh(self) -> None:
        """Atualiza título, botões e ações conforme o estado atual."""
        editing = self._has_doc and self.stack.currentIndex() == 1
        dirty = self.is_dirty()
        if editing:
            self.setWindowTitle(f"{self.doc_name()}{' •' if dirty else ''} — {APP_NAME}")
        else:
            self.setWindowTitle(APP_NAME)
        self.title_label.setText(self.doc_name())
        if self.path:
            note = os.path.basename(self.path)
            if dirty:
                note += "  ·  " + _("alterações não salvas")
        else:
            note = _("Ainda não foi salvo")
        self.file_label.setText(note)
        self.statusBar().setVisible(editing)
        self.undo_btn.setEnabled(self.history.can_undo())
        self.redo_btn.setEnabled(self.history.can_redo())
        has_sel = bool(self.canvas.selection)
        for key, act in self._actions.items():
            if key in ("new", "open", "help"):
                act.setEnabled(True)
            elif key == "undo":
                act.setEnabled(editing and self.history.can_undo())
            elif key == "redo":
                act.setEnabled(editing and self.history.can_redo())
            elif key in ("copy", "cut", "duplicate", "rotate", "front", "back", "delete"):
                act.setEnabled(editing and has_sel)
            else:
                act.setEnabled(editing)

    def _update_theme_button(self) -> None:
        dark = theme.is_dark()
        self.theme_btn.setToolTip(_("Usar o tema claro") if dark else _("Usar o tema escuro"))
        icons.bind(self.theme_btn, "sun" if dark else "moon", "text", 20)

    def _on_selection(self) -> None:
        self.panel.rebuild()
        self._refresh()

    def _on_tool(self, name: str) -> None:
        b = self._tool_buttons.get(name)
        if b is not None:
            b.setChecked(True)
        self.hint_label.setText(self.canvas.hint())
        if not self.canvas.selection:
            self.panel.rebuild()

    def _on_view(self) -> None:
        self.zoom_label.setText(f"{self.canvas.zoom_percent()}%")

    def _on_cursor(self, pt) -> None:
        if pt is None:
            self.coords_label.setText("")
            return
        doc = self.canvas.doc

        def fmt(v: float) -> str:
            return ("-" if v < -1e-9 else "") + render.fmt_len(v, doc)
        self.coords_label.setText(f"x {fmt(pt[0])}   y {fmt(pt[1])}")

    def _set_grid(self, on: bool) -> None:
        self.canvas.show_grid = on
        prefs.settings().setValue("grid", on)
        self.canvas.update()

    def _set_snap(self, on: bool) -> None:
        self.canvas.snap_on = on
        prefs.settings().setValue("snap", on)

    def _set_ortho(self, on: bool) -> None:
        self.canvas.ortho_on = on
        prefs.settings().setValue("ortho", on)

    # ------------------------------------------------------------------------------ telas
    def show_home(self) -> None:
        self.canvas.finish_editor(True)
        self.home.refresh(self._has_doc)
        self.stack.setCurrentIndex(0)

    def show_editor(self) -> None:
        if self._has_doc:
            self.stack.setCurrentIndex(1)
            self.canvas.setFocus()

    def startup(self, files: list[str]) -> None:
        """Logo depois de abrir: oferece a recuperação (se houver) ou abre o arquivo pedido."""
        rec = fileio.read_recovery()
        if rec is not None:
            doc, original, when = rec
            name = doc.title.strip() or (os.path.basename(original) if original else _("Desenho sem título"))
            stamp = QLocale().toString(QDateTime.fromSecsSinceEpoch(int(when)), QLocale.FormatType.ShortFormat)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(APP_NAME)
            box.setText(_("Um desenho não foi salvo da última vez (o computador pode ter desligado)."))
            box.setInformativeText(_("Desenho: {nome}\nÚltima cópia de segurança: {quando}\n\nQuer recuperar esse desenho?")
                                   .format(nome=name, quando=stamp))
            yes = box.addButton(_("Recuperar"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(_("Descartar"), QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(yes)
            box.exec()
            if box.clickedButton() is yes:
                path = original if original and os.path.isfile(original) else None
                self._open_document(doc, path, dirty=True)
                self.statusBar().showMessage(_("Desenho recuperado. Lembre-se de salvar."), 8000)
                return
            fileio.clear_recovery()
        if files:
            self.open_path(files[0])
        else:
            self.show_home()

    # ------------------------------------------------------------------------------ arquivos
    def _open_document(self, doc: Document, path: str | None, dirty: bool = False) -> None:
        self._recovery_timer.stop()
        self.canvas.set_document(doc, fit=True)
        self.path = path
        state = self._state()
        self.history.reset(state)
        self._saved_state = None if dirty else state
        self._has_doc = True
        self.canvas.set_tool("select")
        self.stack.setCurrentIndex(1)
        self.panel.rebuild()
        self._refresh()
        self.canvas.setFocus()

    def maybe_save(self) -> bool:
        """Pergunta se salva as mudanças. False = o usuário cancelou."""
        self.canvas.finish_editor(True)
        if not self.is_dirty():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(APP_NAME)
        box.setText(_("Salvar as mudanças em “{nome}”?").format(nome=self.doc_name()))
        box.setInformativeText(_("Se não salvar, o que foi feito desde a última vez que salvou será perdido."))
        save = box.addButton(_("Salvar"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(_("Não salvar"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(_("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self.save()
        if clicked is discard:
            self._recovery_timer.stop()
            fileio.clear_recovery()
            return True
        return False

    def new_document(self) -> None:
        if not self.maybe_save():
            return
        self._open_document(Document(), None)
        self.canvas.set_tool("beam")

    def open_example(self) -> None:
        if not self.maybe_save():
            return
        self._open_document(samples.mezzanine(), None)

    def _last_dir(self) -> str:
        d = str(prefs.settings().value("last_dir", "") or "")
        if d and os.path.isdir(d):
            return d
        return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or os.path.expanduser("~")

    def _remember_dir(self, path: str) -> None:
        prefs.settings().setValue("last_dir", os.path.dirname(os.path.abspath(path)))

    @staticmethod
    def _filter() -> str:
        return _("Desenho do Autocadinho") + f" (*{FILE_EXT})"

    def open_dialog(self) -> None:
        path, _f = QFileDialog.getOpenFileName(self, _("Abrir desenho"), self._last_dir(),
                                               self._filter() + ";;" + _("Todos os arquivos") + " (*)")
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> bool:
        if not self.maybe_save():
            return False
        try:
            doc = fileio.load(path)
        except fileio.FileError as exc:
            if not os.path.exists(path):
                msg = _("O arquivo não foi encontrado:\n{arquivo}").format(arquivo=path)
                prefs.remove_recent(path)
                self.home.refresh()
            elif str(exc) == "not-a-drawing":
                msg = _("Este arquivo não é um desenho do Autocadinho (ou está danificado).")
            else:
                msg = _("Não foi possível abrir o arquivo.\n\n{erro}").format(erro=exc)
            QMessageBox.warning(self, APP_NAME, msg)
            return False
        self._open_document(doc, os.path.abspath(path))
        prefs.add_recent(path)
        self._remember_dir(path)
        return True

    def save(self) -> bool:
        if not self._has_doc:
            return False
        if not self.path:
            return self.save_as()
        return self._save_to(self.path)

    def save_as(self) -> bool:
        if not self._has_doc:
            return False
        self.canvas.finish_editor(True)
        if self.path:
            start = self.path
        else:
            name = _clean_name(self.canvas.doc.title) or _("Desenho")
            start = os.path.join(self._last_dir(), name + FILE_EXT)
        path, _f = QFileDialog.getSaveFileName(self, _("Salvar desenho"), start, self._filter())
        if not path:
            return False
        if not path.lower().endswith(FILE_EXT):
            path += FILE_EXT
        return self._save_to(path)

    def _save_to(self, path: str) -> bool:
        self.canvas.finish_editor(True)
        doc = self.canvas.doc
        if not doc.title.strip():
            doc.title = os.path.splitext(os.path.basename(path))[0]
            self.commit("title", source="canvas")
        try:
            fileio.save(doc, path, printing.thumbnail_png(doc))
        except fileio.FileError as exc:
            QMessageBox.critical(self, APP_NAME, _("Não foi possível salvar o desenho.\n\n{erro}").format(erro=exc))
            return False
        self.path = os.path.abspath(path)
        self._saved_state = self.history.current
        self._recovery_timer.stop()
        fileio.clear_recovery()
        prefs.add_recent(self.path)
        self._remember_dir(self.path)
        self._refresh()
        self.statusBar().showMessage(_("Desenho salvo: {arquivo}").format(arquivo=self.path), 5000)
        return True

    def _write_recovery(self) -> None:
        if self.is_dirty():
            fileio.write_recovery(self.canvas.doc, self.path)

    # ------------------------------------------------------------------------------ impressão
    def print_dialog(self) -> None:
        if not self._has_doc:
            return
        self.canvas.finish_editor(True)
        from .print_dialog import PrintDialog
        PrintDialog(self, self.canvas.doc, self._export_base()).exec()

    def _export_base(self) -> str:
        """Caminho sugerido (sem extensão) para PDF e imagem: ao lado do desenho ou na última pasta."""
        name = _clean_name(self.doc_name()) or _("Desenho")
        folder = os.path.dirname(self.path) if self.path else self._last_dir()
        return os.path.join(folder, name)

    def export_pdf(self) -> None:
        if self._has_doc:
            from .print_dialog import export_pdf, load_options
            self.canvas.finish_editor(True)
            export_pdf(self, self.canvas.doc, load_options(), self._export_base())

    def export_png(self) -> None:
        if self._has_doc:
            from .print_dialog import export_png, load_options
            self.canvas.finish_editor(True)
            export_png(self, self.canvas.doc, load_options(), self._export_base())

    # ------------------------------------------------------------------------------ edição
    def undo(self) -> None:
        self.canvas.finish_editor(True)
        self.canvas.cancel_operation()
        state = self.history.undo()
        if state is not None:
            self._load_state(state)

    def redo(self) -> None:
        self.canvas.finish_editor(True)
        self.canvas.cancel_operation()
        state = self.history.redo()
        if state is not None:
            self._load_state(state)

    def _load_state(self, state: str) -> None:
        sel = list(self.canvas.selection)
        view = self.canvas.view_state()
        self.canvas.set_document(Document.from_dict(json.loads(state)), fit=False)
        self.canvas.set_view_state(view)
        self.canvas.set_selection(sel)
        self.panel.rebuild()
        if self.is_dirty() and not self._recovery_timer.isActive():
            self._recovery_timer.start()
        self._refresh()

    def cut(self) -> None:
        if self.canvas.copy_selection():
            self.canvas.delete_selection()

    def _context_menu(self, pos: QPoint) -> None:
        if not self._has_doc:
            return
        self._refresh()
        a = self._actions
        menu = QMenu(self)
        if self.canvas.selection:
            for key in ("copy", "cut", "paste", "duplicate"):
                menu.addAction(a[key])
            menu.addSeparator()
            for key in ("rotate", "front", "back"):
                menu.addAction(a[key])
            menu.addSeparator()
            menu.addAction(a["delete"])
        else:
            for key in ("paste", "select_all", "fit"):
                menu.addAction(a[key])
        a["paste"].setEnabled(self.canvas.can_paste())
        menu.exec(pos)
        a["paste"].setEnabled(True)

    def _recolor_actions(self) -> None:
        for act in self._actions.values():
            name = act.property("acIcon")
            if name:
                act.setIcon(icons.icon(str(name)))

    # ------------------------------------------------------------------------------ aparência
    def toggle_theme(self) -> None:
        self.set_theme("light" if theme.is_dark() else "dark")

    def set_theme(self, name: str) -> None:
        theme.set_theme(name)
        prefs.settings().setValue("theme", theme.current().name)
        theme.apply()
        self._apply_titlebar()
        self._recolor_actions()
        self._update_theme_button()
        self.panel.rebuild()
        self.home.refresh()
        self.canvas.update()
        self._refresh()

    def set_language(self, code: str) -> None:
        if code == i18n.language():
            return
        self.canvas.finish_editor(True)
        i18n.set_language(code)
        prefs.settings().setValue("language", code)
        editing = self.stack.currentIndex() == 1
        self._build()
        self.stack.setCurrentIndex(1 if editing and self._has_doc else 0)
        if self.stack.currentIndex() == 0:
            self.home.refresh(self._has_doc)

    def _apply_titlebar(self) -> None:
        """Barra de título do Windows clara ou escura, acompanhando o tema."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            value = ctypes.c_int(1 if theme.is_dark() else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(value),
                                                       ctypes.sizeof(value))
        except Exception:  # noqa: BLE001 (só aparência)
            pass

    # ------------------------------------------------------------------------------ ajuda
    def show_help(self) -> None:
        from .help_dialog import HelpDialog
        HelpDialog(self).exec()

    def show_about(self) -> None:
        text = (f"<h3>{APP_NAME} {__version__}</h3>"
                + "<p>" + _("Desenhos de obra simples, com as medidas certas, prontos para imprimir.") + "</p>"
                + "<p>" + _("Versão {versao} de {data}.").format(versao=__version__, data=__date__) + "<br>"
                + _("Programa livre e gratuito, com licença MIT.") + "</p>"
                + f'<p><a href="{REPO_URL}">{REPO_URL}</a></p>')
        QMessageBox.about(self, _("Sobre o Autocadinho"), text)

    # ------------------------------------------------------------------------------ janela
    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if any(u.toLocalFile().lower().endswith(FILE_EXT) for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:  # noqa: N802
        for u in e.mimeData().urls():
            path = u.toLocalFile()
            if path.lower().endswith(FILE_EXT):
                self.open_path(path)
                return

    def closeEvent(self, e) -> None:  # noqa: N802
        if not self.maybe_save():
            e.ignore()
            return
        self._recovery_timer.stop()
        fileio.clear_recovery()
        prefs.settings().setValue("geometry", self.saveGeometry())
        e.accept()
