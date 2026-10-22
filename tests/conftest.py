"""Ambiente dos testes: preferências e dados numa pasta temporária, e um QApplication para a sessão.

As preferências e a cópia de recuperação de quem usa o app nunca são tocadas: as variáveis
AUTOCADINHO_SETTINGS_DIR e AUTOCADINHO_DATA_DIR apontam para pastas temporárias antes de qualquer
import do app, e a busca automática de atualizações fica desligada. No Windows os testes usam a
plataforma normal do Qt (a "offscreen" de lá não acha fontes) e as janelas são criadas com
WA_DontShowOnScreen, sem aparecer na tela.
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

_TMP = tempfile.mkdtemp(prefix="autocadinho-tests-")
os.environ["AUTOCADINHO_SETTINGS_DIR"] = os.path.join(_TMP, "settings")
os.environ["AUTOCADINHO_DATA_DIR"] = os.path.join(_TMP, "data")
os.environ["AUTOCADINHO_NO_UPDATE_CHECK"] = "1"  # nenhum teste consulta o GitHub
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autocadinho import fileio, i18n  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    from autocadinho.ui import theme
    theme.set_theme("light")
    theme.apply(app)
    yield app


@pytest.fixture(autouse=True)
def _portuguese():
    """Cada teste começa em português, sem preferências salvas nem cópia de recuperação."""
    i18n.set_language("pt_BR")
    fileio.clear_recovery()
    from PySide6.QtCore import QSettings  # noqa: F401  (garante o módulo antes de limpar)
    from autocadinho.ui import prefs
    prefs.settings().clear()
    yield
    i18n.set_language("pt_BR")
    fileio.clear_recovery()
