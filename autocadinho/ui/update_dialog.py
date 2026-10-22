"""Janela de atualização: mostra a versão nova e as novidades, baixa, confere e instala."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
                               QTextBrowser, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__, updater
from ..i18n import N_, _
from . import icons, prefs, theme

ERRORS = {
    "no-public-release": N_("Ainda não há versão publicada para baixar."),
    "offline": N_("Não foi possível falar com o GitHub. Confira a conexão com a internet e tente de novo."),
    "no-checksums": N_("A versão publicada não tem o arquivo de conferência (SHA256SUMS.txt); por segurança, a "
                       "atualização automática foi cancelada. Baixe pela página da versão."),
    "checksum-mismatch": N_("O arquivo baixado não confere com o original publicado. Nada foi instalado."),
    "bad-archive": N_("O pacote baixado não tem o formato esperado. Nada foi instalado."),
    "unsupported": N_("Este tipo de instalação não pode ser atualizado sozinho. Baixe pela página da versão."),
    "cancelled": N_("Download cancelado."),
}


def error_text(code: str) -> str:
    if code in ERRORS:
        return _(ERRORS[code])
    return _("Não foi possível procurar ou instalar a atualização ({codigo}).").format(codigo=code)


class _Bridge(QObject):
    progress = Signal(int, int)
    done = Signal(str, str)  # caminho baixado, erro


class UpdateDialog(QDialog):
    def __init__(self, parent: QWidget | None, release: updater.Release) -> None:
        super().__init__(parent)
        self.release = release
        self._cancel = threading.Event()
        self._busy = False
        version = release.tag.lstrip("v")
        self.setWindowTitle(_("Atualização disponível"))
        self.resize(620, 540)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(10)
        k = QLabel(_("ATUALIZAÇÃO"))
        k.setObjectName("Kicker")
        lay.addWidget(k)
        t = QLabel(_("{app} {nova} está disponível").format(app=APP_NAME, nova=version))
        t.setObjectName("H2")
        lay.addWidget(t)
        sub = QLabel(_("Você está usando a versão {atual}. Seus desenhos e preferências continuam como estão.")
                     .format(atual=__version__))
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        pal = theme.current()
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setStyleSheet(f"QTextBrowser {{ background: {pal.panel2}; border: 1px solid {pal.border}; "
                            f"border-radius: 10px; padding: 10px; }}")
        notes.setMarkdown(release.body or _("Sem notas para esta versão."))
        lay.addWidget(notes, 1)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        skip = QPushButton(_("Pular esta versão"))
        skip.setObjectName("Flat")
        skip.clicked.connect(self._skip)
        row.addWidget(skip)
        page = QPushButton(_("Abrir a página da versão"))
        page.setObjectName("Flat")
        page.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(release.url)))
        row.addWidget(page)
        row.addStretch(1)
        later = QPushButton(_("Agora não"))
        later.clicked.connect(self.reject)
        row.addWidget(later)
        self.go = QPushButton(_("Atualizar agora"))
        self.go.setObjectName("Primary")
        icons.bind(self.go, "download", "on_accent", 18)
        self.go.clicked.connect(self._start)
        row.addWidget(self.go)
        lay.addLayout(row)
        self.bridge = _Bridge()
        self.bridge.progress.connect(self._progress)
        self.bridge.done.connect(self._done)
        self.kind = updater.install_info()["kind"]
        self.asset = updater.pick_asset(release, self.kind)
        if not updater.can_auto_install(self.kind) or self.asset is None:
            self.go.setEnabled(False)
            if self.kind == "source":
                self.status.setText(_("Você está usando o código-fonte: atualize com \"git pull\" ou baixe a versão "
                                      "nova pela página."))
            else:
                self.status.setText(_("Não há pacote automático para esta instalação. Baixe pela página da versão."))

    def _skip(self) -> None:
        prefs.settings().setValue("update_skip", self.release.tag)
        self.reject()

    def _start(self) -> None:
        self._busy = True
        self._cancel.clear()
        self.go.setEnabled(False)
        self.bar.setValue(0)
        self.bar.setVisible(True)
        self.status.setText(_("Baixando {arquivo}…").format(arquivo=self.asset[0]))

        def run() -> None:
            try:
                path = updater.download(self.release, self.asset, lambda d, t: self.bridge.progress.emit(d, t),
                                        self._cancel)
                self.bridge.done.emit(path, "")
            except updater.UpdateError as exc:
                self.bridge.done.emit("", str(exc))
            except Exception as exc:  # noqa: BLE001
                self.bridge.done.emit("", str(exc) or exc.__class__.__name__)

        threading.Thread(target=run, daemon=True).start()

    def _progress(self, done: int, total: int) -> None:
        if total > 0:
            self.bar.setValue(int(done / total * 1000))
            self.status.setText(_("Baixando… {feito} de {total} MB").format(feito=f"{done / 1e6:.0f}",
                                                                            total=f"{total / 1e6:.0f}"))

    def _done(self, path: str, err: str) -> None:
        self._busy = False
        self.bar.setVisible(False)
        if self._cancel.is_set():  # fechou a janela durante o download: não pergunta mais nada
            return
        if err:
            self.go.setEnabled(True)
            self.status.setText(error_text(err))
            return
        self.status.setText(_("Arquivo conferido. O {app} vai fechar para instalar a versão nova e abrir de novo "
                              "sozinho.").format(app=APP_NAME))
        r = QMessageBox.question(self, _("Instalar a atualização"),
                                 _("Tudo pronto. Fechar o {app} agora para instalar a versão {versao}?")
                                 .format(app=APP_NAME, versao=self.release.tag.lstrip("v")))
        if r != QMessageBox.StandardButton.Yes:
            self.go.setEnabled(True)
            return
        win = self.parent()
        # Fecha a janela antes (ela pergunta se quer salvar); se a pessoa cancelar, nada é instalado.
        if win is not None and not win.close():
            self.go.setEnabled(True)
            self.status.setText(_("A instalação ficou para depois: o desenho não foi fechado."))
            return
        try:
            updater.install(path, self.kind)
        except updater.UpdateError as exc:
            QMessageBox.warning(self, _("Atualização"), error_text(str(exc)))
            if win is not None:
                win.show()
            self.go.setEnabled(True)
            return
        self.accept()
        QApplication.instance().exit(0)

    def reject(self) -> None:
        if self._busy:
            self._cancel.set()
        super().reject()
