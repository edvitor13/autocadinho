r"""Gera os ícones do app em assets/ a partir do logotipo desenhado em código (ui/icons.py).

Uso:  .venv\Scripts\python tools\make_assets.py

Saída: assets/logo.ico (16 a 256 px, para o .exe e o instalador), assets/documento.ico (os arquivos
.cadinho no Explorador), assets/logo-256.png e assets/logo-512.png. O assets/logo.svg é mantido à mão
com o mesmo desenho do logotipo.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen  # noqa: E402

from autocadinho.ui import icons  # noqa: E402

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def logo_image(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    icons.paint_logo(p, size)
    p.end()
    return img


def document_image(size: int) -> QImage:
    """Ícone dos desenhos .cadinho: uma folha com a ponta dobrada e o logotipo."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 32.0
    p.scale(s, s)
    pen = QPen(QColor("#8a94a0"), max(1.0, size / 64) / s)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    sheet = QPainterPath()
    for i, (x, y) in enumerate(((5.5, 1.5), (20, 1.5), (26.5, 8), (26.5, 30.5), (5.5, 30.5))):
        sheet.moveTo(x, y) if i == 0 else sheet.lineTo(x, y)
    sheet.closeSubpath()
    p.setBrush(QColor("#ffffff"))
    p.drawPath(sheet)
    fold = QPainterPath()
    fold.moveTo(20, 1.5)
    fold.lineTo(20, 8)
    fold.lineTo(26.5, 8)
    fold.closeSubpath()
    p.setBrush(QColor("#dfe4ea"))
    p.drawPath(fold)
    p.translate(8, 12)
    icons.paint_logo(p, 16)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(data.data())


def write_ico(path: Path, paint=logo_image, sizes=ICO_SIZES) -> None:
    """.ico com uma imagem PNG por tamanho (formato aceito desde o Windows Vista)."""
    images = [png_bytes(paint(s)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for s, data in zip(sizes, images):
        dim = 0 if s >= 256 else s  # 0 quer dizer 256 no formato .ico
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + entries + b"".join(images))


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    write_ico(out / "logo.ico")
    write_ico(out / "documento.ico", document_image)
    for s in (256, 512):
        logo_image(s).save(str(out / f"logo-{s}.png"))
    print("ícones gerados em", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
