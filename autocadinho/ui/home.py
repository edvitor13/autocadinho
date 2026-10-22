"""Tela inicial: começar um desenho novo, abrir um salvo, ver o exemplo e os desenhos recentes."""

from __future__ import annotations

import os

from PySide6.QtCore import QDateTime, QLocale, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QScrollArea, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, fileio
from ..i18n import _
from . import icons, prefs

CARD_W, CARD_H = 216, 196
THUMB_W, THUMB_H = 196, 130


class HomePage(QScrollArea):
    newRequested = Signal()
    openRequested = Signal()
    exampleRequested = Signal()
    backRequested = Signal()
    recentRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._has_doc = False
        self._cols = 0
        self._thumbs: dict[str, tuple[float, QPixmap | None]] = {}
        self.refresh()

    def refresh(self, has_doc: bool | None = None) -> None:
        if has_doc is not None:
            self._has_doc = has_doc
        page = QWidget()
        page.setObjectName("Home")
        outer = QHBoxLayout(page)
        outer.setContentsMargins(32, 40, 32, 40)
        outer.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(0)
        outer.addLayout(col, 0)
        outer.addStretch(1)
        self._content_width = max(CARD_W, min(1000, self.viewport().width() - 64))
        holder = QWidget()
        holder.setFixedWidth(self._content_width)
        col.addWidget(holder)
        col.addStretch(1)
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hero = QHBoxLayout()
        hero.setSpacing(18)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(76))
        hero.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("Hero")
        texts.addWidget(title)
        sub = QLabel(_("Desenhos de obra simples, com as medidas certas, prontos para imprimir."))
        sub.setObjectName("HeroSub")
        sub.setWordWrap(True)
        texts.addWidget(sub)
        hero.addLayout(texts, 1)
        lay.addLayout(hero)
        lay.addSpacing(30)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        if self._has_doc:
            actions.addWidget(self._big(_("Voltar ao desenho"), "plan", self.backRequested.emit, primary=True))
            actions.addWidget(self._big(_("Novo desenho"), "new", self.newRequested.emit))
        else:
            actions.addWidget(self._big(_("Novo desenho"), "new", self.newRequested.emit, primary=True))
        actions.addWidget(self._big(_("Abrir desenho…"), "open", self.openRequested.emit))
        actions.addWidget(self._big(_("Ver um exemplo"), "plan", self.exampleRequested.emit))
        actions.addStretch(1)
        lay.addLayout(actions)
        lay.addSpacing(36)

        h2 = QLabel(_("Desenhos recentes"))
        h2.setObjectName("H2")
        lay.addWidget(h2)
        lay.addSpacing(12)
        recent = prefs.recent_files()
        if not recent:
            empty = QLabel(_("Os desenhos que você salvar vão aparecer aqui, para abrir com um clique."))
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            lay.addWidget(empty)
        else:
            grid = QGridLayout()
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)
            self._cols = max(1, (self._content_width + 14) // (CARD_W + 14))
            for i, path in enumerate(recent):
                grid.addWidget(self._card(path), i // self._cols, i % self._cols)
            grid.setColumnStretch(self._cols, 1)
            lay.addLayout(grid)
        lay.addSpacing(28)
        tip = QLabel(_("Dica: o Autocadinho guarda uma cópia de segurança enquanto você desenha. "
                       "Se o computador desligar sem salvar, ele oferece recuperar o desenho."))
        tip.setObjectName("Faint")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        # setWidget() apagaria o antigo na hora; tirado antes, ele some depois (pode estar no meio de um clique).
        old = self.takeWidget()
        self.setWidget(page)
        if old is not None:
            old.deleteLater()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        width = max(CARD_W, min(1000, self.viewport().width() - 64))
        if abs(width - getattr(self, "_content_width", 0)) > 2:
            self.refresh()

    def _big(self, text: str, icon_name: str, slot, primary: bool = False) -> QToolButton:
        b = QToolButton()
        b.setObjectName("BigPrimary" if primary else "Big")
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        icons.bind(b, icon_name, "on_accent" if primary else "accent", 24)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(58)
        b.clicked.connect(slot)
        return b

    def _thumb(self, path: str) -> QPixmap | None:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        cached = self._thumbs.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        data = fileio.read_thumbnail(path)
        pm = None
        if data:
            img = QImage.fromData(data, "PNG")
            if not img.isNull():
                pm = QPixmap.fromImage(img.scaled(QSize(THUMB_W * 2, THUMB_H * 2), Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
                pm.setDevicePixelRatio(2.0)
        self._thumbs[path] = (mtime, pm)
        return pm

    def _card(self, path: str) -> QToolButton:
        b = QToolButton()
        b.setObjectName("Recent")
        b.setFixedSize(CARD_W, CARD_H)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        name = os.path.splitext(os.path.basename(path))[0]
        exists = os.path.exists(path)
        if exists:
            when = QDateTime.fromSecsSinceEpoch(int(os.path.getmtime(path)))
            sub = QLocale().toString(when, QLocale.FormatType.ShortFormat)
        else:
            sub = _("Arquivo não encontrado")
        fm = b.fontMetrics()
        b.setText(fm.elidedText(name, Qt.TextElideMode.ElideMiddle, CARD_W - 24) + "\n" + sub)
        pm = self._thumb(path) if exists else None
        if pm is None:
            pm = icons.pixmap("plan", "#c3c8cf", 64)
        b.setIcon(QIcon(pm))
        b.setIconSize(QSize(THUMB_W, THUMB_H))
        b.setToolTip(path)
        b.setEnabled(True)
        b.clicked.connect(lambda: self.recentRequested.emit(path))
        b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        b.customContextMenuRequested.connect(lambda pos, btn=b: self._card_menu(btn, path, pos))
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return b

    def _card_menu(self, btn: QToolButton, path: str, pos) -> None:
        menu = QMenu(self)
        menu.addAction(_("Abrir"), lambda: self.recentRequested.emit(path))
        folder = os.path.dirname(path)
        act = menu.addAction(_("Abrir a pasta"), lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        act.setEnabled(os.path.isdir(folder))
        menu.addSeparator()
        menu.addAction(_("Tirar da lista"), lambda: (prefs.remove_recent(path), self.refresh()))
        menu.exec(btn.mapToGlobal(pos))
