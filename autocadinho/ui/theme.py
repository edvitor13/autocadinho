"""Temas claro (padrão) e escuro: cores, fontes e folha de estilo.

A troca de tema é imediata: `apply()` refaz a paleta e a folha de estilo do app e redesenha os
ícones (veja `icons.refresh_all`). A área de desenho lê as cores daqui a cada pintura; a impressão
e as miniaturas usam sempre papel branco e tinta preta (`render.print_style`).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from ..i18n import N_


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    panel: str
    panel2: str
    panel3: str
    border: str
    border_hi: str
    text: str
    muted: str
    faint: str
    accent: str
    accent_hi: str
    accent_soft: str
    on_accent: str
    danger: str
    danger_soft: str
    canvas: str
    grid_minor: str
    grid_major: str
    ink: str
    shadow: str


LIGHT = Palette(
    name="light",
    bg="#f3f4f6", panel="#ffffff", panel2="#f7f8fa", panel3="#eceef2", border="#e1e4e9", border_hi="#cfd4db",
    text="#1d2127", muted="#5b6470", faint="#98a0ab",
    accent="#e8722c", accent_hi="#f2884a", accent_soft="#fdeee4", on_accent="#ffffff",
    danger="#d4403a", danger_soft="#fbe9e8",
    canvas="#ffffff", grid_minor="#f0f2f5", grid_major="#dde1e7", ink="#1b1f24", shadow="#1a1f2a",
)

DARK = Palette(
    name="dark",
    bg="#14161a", panel="#1c1f25", panel2="#22262d", panel3="#2a2f37", border="#2f343d", border_hi="#3c424d",
    text="#e7e9ec", muted="#a3aab5", faint="#6b7380",
    accent="#f2894a", accent_hi="#f7a26b", accent_soft="#3a281d", on_accent="#1c1108",
    danger="#ef6a64", danger_soft="#3a2222",
    canvas="#181b20", grid_minor="#1f2329", grid_major="#2b3038", ink="#e8eaed", shadow="#000000",
)

THEMES = {"light": LIGHT, "dark": DARK}
THEME_LABELS = {"light": N_("Claro"), "dark": N_("Escuro")}

_current: Palette = LIGHT


def current() -> Palette:
    return _current


def set_theme(name: str) -> Palette:
    global _current
    _current = THEMES.get(name, LIGHT)
    return _current


def is_dark() -> bool:
    return _current.name == "dark"


def qcolor(hex_: str, alpha: float | None = None) -> QColor:
    c = QColor(hex_)
    if alpha is not None:
        c.setAlphaF(alpha)
    return c


def ui_font() -> str:
    fams = set(QFontDatabase.families())
    for f in ("Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "Helvetica Neue", "Arial"):
        if f in fams:
            return f
    return "Sans Serif"


def title_font() -> str:
    fams = set(QFontDatabase.families())
    for f in ("Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI", "Inter", "Arial"):
        if f in fams:
            return f
    return ui_font()


def font(size: float = 10.0, weight: QFont.Weight = QFont.Weight.Normal, title: bool = False) -> QFont:
    f = QFont(title_font() if title else ui_font())
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def qpalette(t: Palette | None = None) -> QPalette:
    t = t or _current
    p = QPalette()
    roles = QPalette.ColorRole
    p.setColor(roles.Window, QColor(t.bg))
    p.setColor(roles.WindowText, QColor(t.text))
    p.setColor(roles.Base, QColor(t.panel2))
    p.setColor(roles.AlternateBase, QColor(t.panel3))
    p.setColor(roles.Text, QColor(t.text))
    p.setColor(roles.Button, QColor(t.panel))
    p.setColor(roles.ButtonText, QColor(t.text))
    p.setColor(roles.Highlight, QColor(t.accent))
    p.setColor(roles.HighlightedText, QColor(t.on_accent))
    p.setColor(roles.ToolTipBase, QColor(t.panel))
    p.setColor(roles.ToolTipText, QColor(t.text))
    p.setColor(roles.PlaceholderText, QColor(t.faint))
    p.setColor(roles.Link, QColor(t.accent))
    for role in (roles.Text, roles.ButtonText, roles.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.faint))
    return p


def _arrow_png(t: Palette) -> str:
    """Setinha das listas (QComboBox) desenhada na cor do tema."""
    from . import icons
    path = os.path.join(tempfile.gettempdir(), f"autocadinho_seta_{t.name}.png")
    icons.icon("chevron", t.muted, size=12).pixmap(24, 24).save(path)
    return path.replace("\\", "/")


def stylesheet(t: Palette | None = None) -> str:
    t = t or _current
    f = ui_font()
    tf = title_font()
    arrow = _arrow_png(t)
    return f"""
* {{ font-family: "{f}"; font-size: 10pt; color: {t.text}; }}
QMainWindow, QDialog {{ background: {t.bg}; }}
QToolTip {{ background: {t.panel}; color: {t.text}; border: 1px solid {t.border_hi}; padding: 6px 9px; border-radius: 6px; }}
QWidget#TopBar {{ background: {t.panel}; border-bottom: 1px solid {t.border}; }}
QWidget#ToolRail {{ background: {t.panel}; border-right: 1px solid {t.border}; }}
QWidget#Side {{ background: {t.panel}; border-left: 1px solid {t.border}; }}
QWidget#Home {{ background: {t.bg}; }}
QFrame#Card {{ background: {t.panel}; border: 1px solid {t.border}; border-radius: 14px; }}
QFrame#TipCard {{ background: {t.accent_soft}; border: none; border-radius: 12px; }}
QFrame#Sep {{ background: {t.border}; max-width: 1px; min-width: 1px; }}
QFrame#HSep {{ background: {t.border}; max-height: 1px; min-height: 1px; }}
QLabel#AppTitle {{ font-family: "{tf}"; font-size: 13pt; font-weight: 600; }}
QLabel#DocTitle {{ color: {t.muted}; }}
QLabel#Hero {{ font-family: "{tf}"; font-size: 26pt; font-weight: 700; }}
QLabel#HeroSub {{ color: {t.muted}; font-size: 12pt; }}
QLabel#H2 {{ font-family: "{tf}"; font-size: 13pt; font-weight: 600; }}
QLabel#Kicker {{ font-family: "{tf}"; font-size: 8.5pt; font-weight: 700; color: {t.accent}; letter-spacing: 1px; }}
QLabel#Muted {{ color: {t.muted}; }}
QLabel#Faint {{ color: {t.faint}; font-size: 9pt; }}
QLabel#FieldLabel {{ color: {t.muted}; }}
QLabel#TipTitle {{ font-weight: 600; color: {t.text}; }}
QLabel#TipText {{ color: {t.text}; }}
QLabel#Coords {{ color: {t.muted}; font-family: "Cascadia Mono", "Consolas", monospace; font-size: 9pt; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t.border_hi}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t.faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t.border_hi}; border-radius: 4px; min-width: 30px; }}

QPushButton, QToolButton {{
    background: {t.panel}; border: 1px solid {t.border_hi}; border-radius: 8px; padding: 6px 12px; color: {t.text};
}}
QPushButton:hover, QToolButton:hover {{ background: {t.panel3}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {t.border}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {t.faint}; background: {t.panel2}; border-color: {t.border}; }}
QPushButton#Primary, QToolButton#Primary {{ background: {t.accent}; color: {t.on_accent}; border: 1px solid {t.accent}; font-weight: 600; }}
QPushButton#Primary:hover, QToolButton#Primary:hover {{ background: {t.accent_hi}; border-color: {t.accent_hi}; }}
QPushButton#Danger {{ color: {t.danger}; }}
QPushButton#Danger:hover {{ background: {t.danger_soft}; border-color: {t.danger}; }}
QToolButton#Flat, QPushButton#Flat {{ background: transparent; border: 1px solid transparent; padding: 6px 9px; }}
QToolButton#Flat:hover, QPushButton#Flat:hover {{ background: {t.panel3}; }}
QToolButton#Flat:pressed {{ background: {t.border}; }}
QToolButton#Flat:disabled {{ background: transparent; }}
QToolButton#Tool {{
    background: transparent; border: none; border-radius: 10px; padding: 7px 2px 6px 2px;
    color: {t.muted}; font-size: 8.5pt;
}}
QToolButton#Tool:hover {{ background: {t.panel3}; color: {t.text}; }}
QToolButton#Tool:checked {{ background: {t.accent_soft}; color: {t.accent}; font-weight: 600; }}
QToolButton#Toggle {{ background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 3px 8px; color: {t.muted}; font-size: 9pt; }}
QToolButton#Toggle:hover {{ background: {t.panel3}; }}
QToolButton#Toggle:checked {{ color: {t.accent}; background: {t.accent_soft}; }}
QToolButton#Swatch {{ border-radius: 13px; padding: 0; border: 2px solid {t.border_hi}; min-width: 22px; min-height: 22px; max-width: 22px; max-height: 22px; }}
QToolButton#Swatch:checked {{ border: 2px solid {t.accent}; }}
QToolButton#Recent {{ background: {t.panel}; border: 1px solid {t.border}; border-radius: 14px; padding: 8px; text-align: left; }}
QToolButton#Recent:hover {{ border-color: {t.accent}; background: {t.panel}; }}
QToolButton#Big {{ background: {t.panel}; border: 1px solid {t.border}; border-radius: 14px; padding: 14px 18px; font-size: 11pt; font-weight: 600; text-align: left; }}
QToolButton#Big:hover {{ border-color: {t.accent}; }}
QToolButton#BigPrimary {{ background: {t.accent}; border: 1px solid {t.accent}; border-radius: 14px; padding: 14px 18px; font-size: 11pt; font-weight: 600; color: {t.on_accent}; }}
QToolButton#BigPrimary:hover {{ background: {t.accent_hi}; border-color: {t.accent_hi}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QWidget#ZoomBox {{ background: {t.panel}; border: 1px solid {t.border}; border-radius: 10px; }}
QWidget#ZoomBox QToolButton {{ background: transparent; border: none; padding: 5px 7px; border-radius: 7px; }}
QWidget#ZoomBox QToolButton:hover {{ background: {t.panel3}; }}
QLabel#ZoomLabel {{ color: {t.muted}; font-size: 9pt; min-width: 44px; qproperty-alignment: AlignCenter; }}

QComboBox {{
    background: {t.panel2}; border: 1px solid {t.border_hi}; border-radius: 8px; padding: 5px 10px; min-height: 20px;
}}
QComboBox:hover {{ border-color: {t.faint}; }}
QComboBox:focus {{ border-color: {t.accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url("{arrow}"); width: 10px; height: 10px; margin-right: 8px; }}
QComboBox QAbstractItemView {{
    background: {t.panel}; border: 1px solid {t.border_hi}; selection-background-color: {t.accent_soft};
    selection-color: {t.text}; outline: 0; padding: 4px;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background: {t.panel2}; border: 1px solid {t.border_hi}; border-radius: 8px; padding: 5px 8px;
    selection-background-color: {t.accent}; selection-color: {t.on_accent};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{ border-color: {t.accent}; }}
QLineEdit#Inline {{ background: {t.panel}; border: 2px solid {t.accent}; border-radius: 6px; padding: 2px 6px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {t.border_hi}; background: {t.panel2}; }}
QCheckBox::indicator:hover {{ border-color: {t.accent}; }}
QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.accent}; image: url("{_check_png(t)}"); }}

QMenu {{ background: {t.panel}; border: 1px solid {t.border_hi}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t.accent_soft}; color: {t.text}; }}
QMenu::item:disabled {{ color: {t.faint}; }}
QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; margin-left: 6px; }}

QStatusBar {{ background: {t.panel}; border-top: 1px solid {t.border}; color: {t.muted}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {t.muted}; font-size: 9pt; padding: 0 6px; }}
QTextBrowser {{ background: {t.panel}; border: 1px solid {t.border}; border-radius: 12px; padding: 10px; }}
QSplitter::handle {{ background: {t.border}; }}
"""


def _check_png(t: Palette) -> str:
    from . import icons
    path = os.path.join(tempfile.gettempdir(), f"autocadinho_check_{t.name}.png")
    icons.icon("check", t.on_accent, size=14).pixmap(28, 28).save(path)
    return path.replace("\\", "/")


def apply(app: QApplication | None = None) -> None:
    """Aplica o tema atual ao app inteiro (paleta, folha de estilo e ícones)."""
    app = app or QApplication.instance()
    if app is None:
        return
    app.setPalette(qpalette())
    app.setStyleSheet(stylesheet())
    from . import icons
    icons.refresh_all()
