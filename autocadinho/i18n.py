"""Tradução da interface (português do Brasil e inglês).

O texto-fonte do código é o português do Brasil. O inglês fica em `autocadinho/locales/en.json`,
que mapeia o texto em português para a tradução:

    from .i18n import _
    botao.setText(_("Abrir"))
    msg = _("{n} itens selecionados").format(n=3)

Tabelas montadas na importação (antes de o idioma ser escolhido) usam `N_()` e são traduzidas
com `_()` na hora de aparecer. Sem tradução, o texto em português é mostrado.
"""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path

SOURCE = "pt_BR"
LANGUAGES: dict[str, str] = {
    "pt_BR": "Português (Brasil)",
    "en": "English",
}

_lang = SOURCE
_catalog: dict[str, str] = {}


def locales_dir() -> Path:
    return Path(__file__).resolve().parent / "locales"


def load_catalog(code: str) -> dict[str, str]:
    if code == SOURCE:
        return {}
    try:
        data = json.loads((locales_dir() / f"{code}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and v and not k.startswith("@")}


def set_language(code: str) -> str:
    """Ativa um idioma (código de LANGUAGES). Devolve o código efetivamente usado."""
    global _lang, _catalog
    if code not in LANGUAGES:
        code = "en"
    _lang = code
    _catalog = load_catalog(code)
    try:  # datas no formato do idioma (22/10/2026 ou 10/22/2026)
        from PySide6.QtCore import QLocale
        QLocale.setDefault(QLocale("pt_BR" if code == "pt_BR" else "en_US"))
    except ImportError:
        pass
    return code


def language() -> str:
    return _lang


def _(text: str) -> str:
    """Traduz um texto escrito em português do Brasil."""
    if not _catalog or not text:
        return text
    return _catalog.get(text, text)


def N_(text: str) -> str:
    """Marca um texto para o catálogo sem traduzir agora (traduza com `_()` ao mostrar)."""
    return text


def decimal_sep() -> str:
    """Separador decimal do idioma ativo: vírgula (português) ou ponto (inglês)."""
    return "." if _lang == "en" else ","


def fmt_decimal(value: float, decimals: int = 2) -> str:
    """Número com casas decimais e o separador do idioma (1,50 / 1.50)."""
    return f"{value:.{decimals}f}".replace(".", decimal_sep())


def system_language() -> str:
    """Português se o sistema estiver em português; senão inglês."""
    candidates = []
    try:
        from PySide6.QtCore import QLocale
        candidates += [QLocale.system().name()] + list(QLocale.system().uiLanguages())
    except Exception:  # noqa: BLE001
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var):
            candidates.append(os.environ[var])
    try:
        candidates.append(locale.getlocale()[0] or "")
    except (ValueError, TypeError):
        pass
    for c in candidates:
        c = (c or "").replace("-", "_").lower()
        if c == "pt" or c.startswith(("pt_", "pt.", "portuguese")):
            return "pt_BR"
        if c == "en" or c.startswith(("en_", "en.", "english")):
            return "en"
    return "en"
