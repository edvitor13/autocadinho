import json

import pytest

from autocadinho import i18n
from autocadinho.model import (KINDS, Beam, Dimension, Document, Element, Line, Pillar, Rect, Text, selection_center)


def sample_doc() -> Document:
    doc = Document(title="Teste")
    doc.add(Beam(x1=0, y1=0, x2=300, y2=0, label="VIGA 1", color="#d64541"))
    doc.add(Line(x1=0, y1=50, x2=0, y2=250, dashed=True, width=2))
    doc.add(Pillar(x=300, y=0, w=20, h=40, label="P1", label_dx=-30, label_dy=10))
    doc.add(Rect(x=10, y=20, w=100, h=60, fill=True, show_dims=True))
    doc.add(Text(x=50, y=50, text="Laje\n10 cm", size=12, bold=True, rot=90))
    doc.add(Dimension(x1=0, y1=0, x2=300, y2=0, offset=-40, text=""))
    return doc


def test_every_kind_is_registered():
    assert set(KINDS) == {"beam", "line", "pillar", "rect", "text", "dim", "ellipse", "poly", "symbol"}


def test_round_trip_keeps_everything():
    doc = sample_doc()
    data = json.loads(json.dumps(doc.to_dict()))
    again = Document.from_dict(data)
    assert again.to_dict() == doc.to_dict()
    assert [type(e) for e in again.elements] == [Beam, Line, Pillar, Rect, Text, Dimension]


def test_unknown_kinds_and_bad_values_are_tolerated():
    data = {
        "title": 5,
        "settings": {"unit": "km", "label_size": 99999, "snap_step": "abc", "beam_prefix": "  PAREDE  "},
        "elements": [
            {"kind": "spaceship", "x": 1},
            "lixo",
            {"kind": "beam", "x1": "10", "y1": None, "x2": float("nan"), "width": "grossa", "label": 7},
            {"kind": "pillar", "id": "a", "label_dx": "x"},
            {"kind": "pillar", "id": "a"},
        ],
    }
    doc = Document.from_dict(data)
    assert doc.title == "5"
    assert doc.unit == "m"
    assert doc.label_size == 500.0
    assert doc.snap_step == 10.0
    assert doc.beam_prefix == "PAREDE"
    beam, p1, p2 = doc.elements
    assert beam.x1 == 10.0 and beam.y1 == 0.0 and beam.x2 == 0.0 and beam.width == 15.0 and beam.label == "7"
    assert p1.label_dx is None
    assert p1.id != p2.id  # id repetido ganha um novo


def test_from_dict_rejects_non_dict():
    with pytest.raises(ValueError):
        Document.from_dict([])
    with pytest.raises(ValueError):
        Element.from_dict({"kind": "nada"})


def test_next_label_numbering():
    doc = Document()
    assert doc.next_label("VIGA") == "VIGA 1"
    doc.add(Beam(label="VIGA 1"))
    doc.add(Beam(label="viga 7"))
    doc.add(Beam(label="VIGA X"))
    assert doc.next_label("VIGA") == "VIGA 8"
    assert doc.next_label("P") == "P1"
    doc.add(Pillar(label="P3"))
    assert doc.next_label("P") == "P4"
    assert doc.next_label("") == ""
    assert doc.next_label("   ") == ""


def test_default_prefixes_follow_language():
    assert Document().beam_prefix == "VIGA"
    assert Document().pillar_prefix == "P"
    i18n.set_language("en")
    assert Document().beam_prefix == "BEAM"
    assert Document().pillar_prefix == "C"
    # um desenho salvo em português continua com os nomes dele
    doc = Document.from_dict({"settings": {"beam_prefix": "VIGA", "pillar_prefix": "P"}, "elements": []})
    assert (doc.beam_prefix, doc.pillar_prefix) == ("VIGA", "P")


def test_segment_length_and_set_length():
    b = Beam(x1=0, y1=0, x2=0, y2=200)
    assert b.length() == 200
    b.set_length(350)
    assert (b.x2, b.y2) == (0, 350)


def test_rotate_selection_moves_and_turns():
    doc = sample_doc()
    beam = doc.elements[0]
    pillar = doc.elements[2]
    beam.rotate90((0, 0))
    assert (beam.x1, beam.y1, beam.x2, beam.y2) == (0, 0, 0, 300)
    pillar.rotate90((300, 0))
    assert (pillar.x, pillar.y, pillar.w, pillar.h) == (300, 0, 40, 20)
    assert (pillar.label_dx, pillar.label_dy) == (-10, -30)
    t = doc.elements[4]
    t.rotate90((0, 0))
    assert t.rot == 0
    r = Rect(x=0, y=0, w=100, h=50)
    r.rotate90((0, 0))
    assert (r.x, r.y, r.w, r.h) == (-50, 0, 50, 100)


def test_order_and_removal():
    doc = sample_doc()
    ids = [e.id for e in doc.elements]
    doc.bring_front([ids[0]])
    assert doc.elements[-1].id == ids[0]
    doc.send_back([ids[0], ids[3]])
    assert [e.id for e in doc.elements[:2]] == [ids[3], ids[0]]  # mantém a ordem entre eles
    assert doc.remove([ids[1], "nao-existe"]) == 1
    assert doc.get(ids[1]) is None
    assert doc.count("beam") == 1


def test_clone_gets_new_id_and_copy_is_deep():
    doc = sample_doc()
    el = doc.elements[0]
    c = el.clone()
    assert c.id != el.id and c.to_dict() | {"id": el.id} == el.to_dict()
    cp = doc.copy()
    cp.elements[0].x1 = 999
    assert doc.elements[0].x1 == 0


def test_selection_center():
    assert selection_center([]) == (0.0, 0.0)
    assert selection_center([Pillar(x=0, y=0), Pillar(x=100, y=40)]) == (50, 20)


def test_dimension_normal_side():
    d = Dimension(x1=0, y1=0, x2=100, y2=0)
    assert d.normal() == (0.0, -1.0)  # offset positivo afasta para cima de uma medida da esquerda para a direita
