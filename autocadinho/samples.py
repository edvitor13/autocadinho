"""Desenho de exemplo: a planta de um mezanino com vigas, pilares e medidas.

Montado em código (e não lido de um arquivo) para os nomes saírem no idioma do app.
"""

from __future__ import annotations

from . import render
from .i18n import _
from .model import Beam, Dimension, Document, Labeled, Pillar

W, H = 1000.0, 620.0  # 10,00 m × 6,20 m

# (x1, y1, x2, y2, lado do nome, deslocamento do nome ao longo da viga em cm)
# lado "auto" = acima (horizontais) ou à esquerda (verticais)
BEAMS = [
    (0, H, W, H, "below", 0),          # 1
    (0, 0, W, 0, "auto", 0),           # 2
    (W, 0, W, H, "right", 0),          # 3
    (910, 0, 910, H, "auto", 0),       # 4
    (650, 0, 650, H, "auto", 0),       # 5
    (340, 0, 340, H, "auto", 0),       # 6
    (0, 0, 0, H, "auto", 0),           # 7
    (340, 470, W, 470, "auto", -175),  # 8
    (650, 170, W, 170, "auto", -90),   # 9
    (0, 110, 340, 110, "auto", 0),     # 10
    (110, 0, 110, 110, "standing", 0),  # 11
]

# (x, y, deitado?, posição do nome relativa ao centro ou None = automática)
PILLARS = [
    (W, 30, False, None),          # 1
    (770, 0, True, None),          # 2
    (475, 0, True, None),          # 3
    (185, 0, True, None),          # 4
    (0, 30, False, None),          # 5
    (0, 590, False, None),         # 6
    (340, 620, True, (-55, -42)),  # 7
    (650, 620, True, (-55, -42)),  # 8
    (W, 590, False, None),         # 9
    (910, 670, False, None),       # 10
    (910, 370, False, None),       # 11
    (830, 170, False, (-45, 45)),  # 12
]


def _flip_label(el: Labeled, doc: Document, sx: float, sy: float) -> None:
    render.materialize_label(el, doc)
    el.label_dx = (el.label_dx or 0.0) * sx
    el.label_dy = (el.label_dy or 0.0) * sy


def mezzanine() -> Document:
    doc = Document(title=_("Mezanino (exemplo)"))
    bp, pp = doc.beam_prefix, doc.pillar_prefix
    for i, (x1, y1, x2, y2, side, shift) in enumerate(BEAMS, start=1):
        b = Beam(x1=x1, y1=y1, x2=x2, y2=y2, width=doc.beam_width, label=f"{bp} {i}")
        if side == "standing":
            b.label_rot = 90
        doc.add(b)
        if side == "below":
            _flip_label(b, doc, 1, -1)
        elif side == "right":
            _flip_label(b, doc, -1, 1)
        if shift:
            render.materialize_label(b, doc)
            b.label_dx = (b.label_dx or 0.0) + shift
    for i, (x, y, lying, pos) in enumerate(PILLARS, start=1):
        w, h = (doc.pillar_w, doc.pillar_h) if lying else (doc.pillar_h, doc.pillar_w)
        p = Pillar(x=x, y=y, w=w, h=h, label=f"{pp}{i}")
        if pos is not None:
            p.label_dx, p.label_dy = pos
        doc.add(p)
    doc.add(Dimension(x1=0, y1=H, x2=W, y2=H, offset=-135))
    doc.add(Dimension(x1=W, y1=0, x2=W, y2=H, offset=175))
    return doc
