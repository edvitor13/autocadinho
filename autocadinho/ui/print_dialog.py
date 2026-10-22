"""Janela de impressão: prévia da folha, papel, posição, escala, PDF e imagem.

A prévia é pintada por `printing.render_page`, a mesma função da impressora e do PDF: o que aparece
aqui é o que sai no papel. As escolhas ficam guardadas nas preferências (`print_options`).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from .. import APP_NAME, printing
from ..i18n import _
from ..model import Document
from ..printing import PageOptions
from . import icons, prefs, theme


def load_options() -> PageOptions:
    return PageOptions.from_json(str(prefs.settings().value("print_options", "") or ""))


def save_options(opts: PageOptions) -> None:
    prefs.settings().setValue("print_options", opts.to_json())


def _done(parent: QWidget, text: str, path: str) -> None:
    """Avisa que o arquivo foi salvo e oferece abrir."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(APP_NAME)
    box.setText(text)
    box.setInformativeText(path)
    open_btn = box.addButton(_("Abrir agora"), QMessageBox.ButtonRole.AcceptRole)
    box.addButton(_("Fechar"), QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is open_btn:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def export_pdf(parent: QWidget, doc: Document, opts: PageOptions, base: str) -> bool:
    path, _f = QFileDialog.getSaveFileName(parent, _("Salvar em PDF"), base + ".pdf", "PDF (*.pdf)")
    if not path:
        return False
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    if not printing.save_pdf(doc, opts, path):
        QMessageBox.critical(parent, APP_NAME, _("Não foi possível salvar o PDF (o arquivo pode estar aberto em "
                                                 "outro programa)."))
        return False
    _done(parent, _("PDF salvo."), path)
    return True


def export_png(parent: QWidget, doc: Document, opts: PageOptions, base: str) -> bool:
    path, _f = QFileDialog.getSaveFileName(parent, _("Salvar como imagem"), base + ".png", _("Imagem PNG") + " (*.png)")
    if not path:
        return False
    if not path.lower().endswith(".png"):
        path += ".png"
    if not printing.save_png(doc, opts, path):
        QMessageBox.critical(parent, APP_NAME, _("Não foi possível salvar a imagem."))
        return False
    _done(parent, _("Imagem salva."), path)
    return True


class PagePreview(QWidget):
    """A folha inteira, do tamanho que couber, sobre um fundo neutro."""

    def __init__(self, dlg: "PrintDialog") -> None:
        super().__init__()
        self.dlg = dlg
        self.setMinimumSize(420, 420)

    def paintEvent(self, e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(t.panel3))
        doc, opts = self.dlg.doc, self.dlg.opts
        pw, ph = printing.page_mm(opts, doc)
        m = 28
        k = min((self.width() - 2 * m) / pw, (self.height() - 2 * m) / ph)
        w, h = pw * k, ph * k
        target = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        for i, a in ((6, 0.05), (3, 0.08), (1, 0.12)):
            p.setBrush(theme.qcolor(t.shadow, a))
            p.drawRoundedRect(target.adjusted(-i + 1, -i + 3, i + 1, i + 3), 3, 3)
        # Pintada numa imagem (e não direto na tela) para o texto pequeno não ganhar franjas coloridas.
        dpr = self.devicePixelRatioF()
        img = QImage(max(1, round(w * dpr)), max(1, round(h * dpr)), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor("#ffffff"))
        ip = QPainter(img)
        printing.render_page(ip, doc, opts, QRectF(0, 0, img.width(), img.height()), (pw, ph))
        ip.end()
        img.setDevicePixelRatio(dpr)
        p.drawImage(target.topLeft(), img)
        p.end()


class PrintDialog(QDialog):
    def __init__(self, parent: QWidget, doc: Document, export_base: str) -> None:
        super().__init__(parent)
        self.doc = doc
        self.base = export_base
        self.opts = load_options()
        self.setWindowTitle(_("Imprimir"))
        self.resize(1040, 700)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.preview = PagePreview(self)
        row.addWidget(self.preview, 1)

        side = QWidget()
        side.setObjectName("Side")
        side.setFixedWidth(330)
        col = QVBoxLayout(side)
        col.setContentsMargins(22, 22, 22, 20)
        col.setSpacing(12)
        title = QLabel(_("Imprimir"))
        title.setObjectName("H2")
        col.addWidget(title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.paper = QComboBox()
        for key in printing.PAPERS:
            self.paper.addItem(_(printing.PAPER_LABELS[key]), key)
        self.orient = QComboBox()
        for key, label in printing.ORIENTATIONS.items():
            self.orient.addItem(_(label), key)
        self.scale = QComboBox()
        for s in printing.SCALES:
            self.scale.addItem(_("Ajustar à folha") if s == 0 else f"1:{s}", s)
        for r, (label, w) in enumerate(((_("Papel"), self.paper), (_("Folha"), self.orient), (_("Escala"), self.scale))):
            lab = QLabel(label)
            lab.setObjectName("FieldLabel")
            grid.addWidget(lab, r, 0)
            grid.addWidget(w, r, 1)
        col.addLayout(grid)

        self.info = QLabel()
        self.info.setObjectName("Muted")
        self.info.setWordWrap(True)
        col.addWidget(self.info)
        self.warn = QFrame()
        self.warn.setObjectName("TipCard")
        wl = QVBoxLayout(self.warn)
        wl.setContentsMargins(12, 10, 12, 12)
        wl.setSpacing(8)
        self.warn_text = QLabel()
        self.warn_text.setObjectName("TipText")
        self.warn_text.setWordWrap(True)
        wl.addWidget(self.warn_text)
        self.fix_btn = QPushButton()
        self.fix_btn.clicked.connect(self._use_best)
        wl.addWidget(self.fix_btn)
        col.addWidget(self.warn)

        sep = QFrame()
        sep.setObjectName("HSep")
        col.addWidget(sep)
        self.header = QCheckBox(_("Título e data no alto da folha"))
        self.mono = QCheckBox(_("Tudo em preto (sem cores)"))
        col.addWidget(self.header)
        col.addWidget(self.mono)
        col.addStretch(1)

        self.print_btn = QPushButton(_("Imprimir…"))
        self.print_btn.setObjectName("Primary")
        icons.bind(self.print_btn, "print", "on_accent", 18)
        self.print_btn.setMinimumHeight(40)
        self.print_btn.clicked.connect(self._print)
        col.addWidget(self.print_btn)
        files = QHBoxLayout()
        files.setSpacing(8)
        pdf = QPushButton(_("PDF…"))
        icons.bind(pdf, "pdf", "text", 18)
        pdf.setToolTip(_("Salvar a folha em PDF, para mandar por e-mail ou WhatsApp"))
        pdf.clicked.connect(lambda: export_pdf(self, self.doc, self.opts, self.base))
        png = QPushButton(_("Imagem…"))
        icons.bind(png, "image", "text", 18)
        png.setToolTip(_("Salvar a folha como imagem PNG"))
        png.clicked.connect(lambda: export_png(self, self.doc, self.opts, self.base))
        files.addWidget(pdf)
        files.addWidget(png)
        col.addLayout(files)
        close = QPushButton(_("Fechar"))
        close.setObjectName("Flat")
        close.clicked.connect(self.reject)
        col.addWidget(close)
        row.addWidget(side)

        self._load_widgets()
        for combo in (self.paper, self.orient, self.scale):
            combo.currentIndexChanged.connect(self._changed)
        self.header.toggled.connect(self._changed)
        self.mono.toggled.connect(self._changed)
        self._update_info()

    def _load_widgets(self) -> None:
        o = self.opts
        self.paper.setCurrentIndex(max(0, self.paper.findData(o.paper)))
        self.orient.setCurrentIndex(max(0, self.orient.findData(o.orientation)))
        self.scale.setCurrentIndex(max(0, self.scale.findData(o.scale)))
        self.header.setChecked(o.header)
        self.mono.setChecked(o.mono)

    def _changed(self) -> None:
        self.opts = PageOptions(self.paper.currentData(), self.orient.currentData(), int(self.scale.currentData()),
                                self.header.isChecked(), self.mono.isChecked())
        save_options(self.opts)
        self._update_info()
        self.preview.update()

    def _update_info(self) -> None:
        lay = printing.compute_layout(self.doc, self.opts)
        self._best = 0
        if lay.bounds is None:
            self.info.setText(_("O desenho está vazio."))
            self.warn.hide()
            return
        if self.opts.scale == 0:
            self.info.setText(_("O desenho ocupa a folha toda, na escala aproximada 1:{n}.").format(n=lay.denom) + " "
                              + _("Para medir no papel com a régua, escolha uma escala exata."))
        else:
            self.info.setText(_("Na escala 1:{n}, 1 cm no papel vale {n} cm na obra.").format(n=lay.denom))
        if lay.fits:
            self.warn.hide()
            return
        self._best = printing.best_scale(self.doc, self.opts)
        if self._best:
            self.warn_text.setText(_("O desenho não cabe na folha em 1:{n}.").format(n=lay.denom))
            self.fix_btn.setText(_("Usar 1:{n}, que cabe").format(n=self._best))
        else:
            self.warn_text.setText(_("O desenho não cabe na folha em 1:{n}. Use um papel maior ou "
                                     "\"Ajustar à folha\".").format(n=lay.denom))
            self.fix_btn.setText(_("Ajustar à folha"))
        self.warn.show()

    def _use_best(self) -> None:
        self.scale.setCurrentIndex(max(0, self.scale.findData(self._best)))

    def _print(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageLayout(printing.page_layout(self.opts, self.doc))
        printer.setFullPage(True)
        printer.setDocName(self.doc.title.strip() or APP_NAME)
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle(_("Imprimir"))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not printing.print_doc(printer, self.doc, self.opts):
            QMessageBox.critical(self, APP_NAME, _("Não foi possível imprimir. Confira se a impressora está ligada."))
            return
        self.accept()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._print()
            return
        super().keyPressEvent(e)
