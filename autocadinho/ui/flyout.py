"""Janelinha que abre ao lado de um botão da coluna de ferramentas, com as opções em quadradinhos.

Usada pelos grupos "Formas" e "Símbolos": cada quadradinho tem ícone e nome; escolher um fecha a
janelinha e avisa com `chosen(chave)`. Fecha também com Esc ou clicando fora (é um popup).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from . import icons


class Flyout(QFrame):
    chosen = Signal(str)
    closed = Signal()

    def __init__(self, parent: QWidget, title: str, items: list[tuple[str, str, str, str]], current: str | None,
                 columns: int = 3) -> None:
        """`items`: (chave, nome, ícone, tecla de atalho ou "")."""
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if parent.window().testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen):  # testes e capturas
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("Flyout")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        k = QLabel(title.upper())
        k.setObjectName("Kicker")
        lay.addWidget(k)
        grid = QGridLayout()
        grid.setSpacing(4)
        self.buttons: dict[str, QToolButton] = {}
        for i, (key, label, icon_name, shortcut) in enumerate(items):
            b = QToolButton()
            b.setObjectName("Tile")
            b.setCheckable(True)
            b.setChecked(key == current)
            b.setText(label)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            icons.bind(b, icon_name, "text", 28, on_role="accent")
            b.setToolTip(f"{label} ({shortcut})" if shortcut else label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(106, 76)
            b.clicked.connect(lambda _c=False, key=key: self._choose(key))
            grid.addWidget(b, i // columns, i % columns)
            self.buttons[key] = b
        lay.addLayout(grid)

    def _choose(self, key: str) -> None:
        self.chosen.emit(key)
        self.close()

    def popup(self, pos: QPoint) -> None:
        """Mostra a janelinha em `pos` (tela), sem passar da borda do monitor."""
        self.adjustSize()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = max(min(pos.x(), area.right() - self.width()), area.left())
        y = max(min(pos.y(), area.bottom() - self.height()), area.top())
        self.move(x, y)
        self.show()
        b = next((b for b in self.buttons.values() if b.isChecked()), None)
        (b or next(iter(self.buttons.values()))).setFocus()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(e)
