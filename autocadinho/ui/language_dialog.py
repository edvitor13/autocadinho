"""Escolha do idioma no primeiro acesso (depois, pelo menu de três pontinhos > Idioma)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import APP_NAME, i18n
from . import icons, theme

# Textos desta janela nos dois idiomas (ela aparece antes de existir um idioma escolhido).
TEXTS = {
    "pt_BR": ("Escolha o idioma", "Dá para trocar depois, no menu ⋯ > Idioma.", "Continuar"),
    "en": ("Choose your language", "You can change it later in the ⋯ menu > Language.", "Continue"),
}
CAPTIONS = {"pt_BR": "Brasil", "en": "English"}


class LangCard(QAbstractButton):
    def __init__(self, code: str, parent=None) -> None:
        super().__init__(parent)
        self.code = code
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(QSize(210, 92))
        self._hover = False

    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        p.setPen(QPen(QColor(t.accent if on or self._hover else t.border_hi), 2 if on else 1))
        p.setBrush(QColor(t.accent_soft if on else t.panel))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QColor(t.text))
        p.setFont(theme.font(13, QFont.Weight.DemiBold, title=True))
        p.drawText(r.adjusted(16, 14, -40, -36), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   i18n.LANGUAGES[self.code])
        p.setPen(QColor(t.muted))
        p.setFont(theme.font(9))
        p.drawText(r.adjusted(16, 50, -12, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   CAPTIONS[self.code])
        if on:
            p.drawPixmap(int(r.right()) - 32, int(r.top()) + 12, icons.pixmap("check", t.accent, 20))
        p.end()


class LanguageDialog(QDialog):
    def __init__(self, parent=None, current: str | None = None) -> None:
        super().__init__(parent)
        self.selected = current or i18n.system_language()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.app_icon())
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(16)
        top = QHBoxLayout()
        top.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(48))
        top.addWidget(logo)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title = QLabel()
        self.title.setObjectName("H2")
        texts.addWidget(self.title)
        self.sub = QLabel()
        self.sub.setObjectName("Muted")
        texts.addWidget(self.sub)
        top.addLayout(texts, 1)
        lay.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.group = QButtonGroup(self)
        self.cards: dict[str, LangCard] = {}
        for code in i18n.LANGUAGES:
            card = LangCard(code)
            self.group.addButton(card)
            row.addWidget(card)
            self.cards[code] = card
            card.clicked.connect(lambda _c=False, c=code: self._pick(c))
        lay.addLayout(row)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.ok = QPushButton()
        self.ok.setObjectName("Primary")
        self.ok.setMinimumWidth(140)
        self.ok.clicked.connect(self.accept)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)
        self._pick(self.selected if self.selected in self.cards else "en")

    def _pick(self, code: str) -> None:
        self.selected = code
        self.cards[code].setChecked(True)
        title, sub, ok = TEXTS[code]
        self.title.setText(title)
        self.sub.setText(sub)
        self.ok.setText(ok)
        for card in self.cards.values():
            card.update()
