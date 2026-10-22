"""Onde ficam as preferências do app (idioma, tema, recentes, opções de impressão).

Por padrão, no lugar nativo do sistema (registro do Windows, ~/.config no Linux). Com a variável
AUTOCADINHO_SETTINGS_DIR definida — testes automatizados — tudo vai para um .ini nessa pasta.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

from .. import APP_NAME

MAX_RECENT = 12


def settings() -> QSettings:
    folder = os.environ.get("AUTOCADINHO_SETTINGS_DIR")
    if folder:
        os.makedirs(folder, exist_ok=True)
        return QSettings(os.path.join(folder, f"{APP_NAME}.ini"), QSettings.Format.IniFormat)
    return QSettings(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, APP_NAME, APP_NAME)


def get_bool(key: str, default: bool) -> bool:
    v = settings().value(key, default)
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes")
    return bool(v)


def recent_files() -> list[str]:
    v = settings().value("recent", [])
    if isinstance(v, str):
        v = [v] if v else []
    return [str(x) for x in (v or []) if x]


def add_recent(path: str) -> None:
    path = os.path.abspath(path)
    items = [p for p in recent_files() if os.path.normcase(p) != os.path.normcase(path)]
    settings().setValue("recent", [path] + items[: MAX_RECENT - 1])


def remove_recent(path: str) -> None:
    settings().setValue("recent", [p for p in recent_files() if os.path.normcase(p) != os.path.normcase(path)])
