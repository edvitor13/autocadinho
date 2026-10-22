import json
import os

import pytest

from autocadinho import fileio
from autocadinho.history import History
from autocadinho.model import Beam, Document, Pillar


# ------------------------------------------------------------------------------------- histórico
def test_undo_redo():
    h = History()
    h.reset("a")
    assert not h.can_undo()
    assert h.push("b")
    assert h.push("c")
    assert not h.push("c")  # nada mudou
    assert h.undo() == "b"
    assert h.undo() == "a"
    assert h.undo() is None
    assert h.redo() == "b"
    assert h.push("d")  # um passo novo apaga o "refazer"
    assert not h.can_redo()
    assert h.current == "d"


def test_steps_with_same_key_merge():
    h = History()
    h.reset("a")
    h.push("ab", key="label:1")
    h.push("abc", key="label:1")
    h.push("abcd", key="label:1")
    assert h.undo() == "a"
    h.redo()
    h.push("x", key="label:2")
    assert h.undo() == "abcd"


def test_steps_without_key_never_merge():
    h = History()
    h.reset("a")
    h.push("b")
    h.push("c")
    assert h.undo() == "b"


def test_history_limit():
    h = History(limit=5)
    h.reset("0")
    for i in range(1, 20):
        h.push(str(i))
    n = 0
    while h.undo() is not None:
        n += 1
    assert n == 4
    assert h.current == "15"


# ------------------------------------------------------------------------------------- arquivos
def drawing() -> Document:
    doc = Document(title="Garagem")
    doc.add(Beam(x1=0, y1=0, x2=500, y2=0, label="VIGA 1"))
    doc.add(Pillar(x=0, y=0, label="P1"))
    return doc


def test_save_and_load(tmp_path):
    path = tmp_path / "garagem.cadinho"
    fileio.save(drawing(), path, thumbnail_png=b"\x89PNG fake")
    assert [p.name for p in tmp_path.iterdir()] == ["garagem.cadinho"]  # sem temporário sobrando
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["app"] == "Autocadinho" and data["format"] == 1 and "version" in data
    doc = fileio.load(path)
    assert doc.to_dict() == drawing().to_dict() | {"elements": doc.to_dict()["elements"]}
    assert [e.label for e in doc.elements] == ["VIGA 1", "P1"]
    assert fileio.read_thumbnail(path) == b"\x89PNG fake"


def test_load_accepts_bom(tmp_path):
    path = tmp_path / "bom.cadinho"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(drawing().to_dict()).encode("utf-8"))
    assert fileio.load(path).title == "Garagem"


@pytest.mark.parametrize("content", [b"", b"nao e json", b"[1, 2]", b'{"title": "sem elementos"}', b"\xff\xfe\x00"])
def test_load_rejects_other_files(tmp_path, content):
    path = tmp_path / "x.cadinho"
    path.write_bytes(content)
    with pytest.raises(fileio.FileError, match="not-a-drawing"):
        fileio.load(path)
    assert fileio.read_thumbnail(path) is None


def test_load_missing_file(tmp_path):
    with pytest.raises(fileio.FileError):
        fileio.load(tmp_path / "nao-existe.cadinho")


def test_atomic_write_keeps_old_file_on_error(tmp_path, monkeypatch):
    path = tmp_path / "a.cadinho"
    path.write_bytes(b"antigo")

    def boom(*args, **kwargs):
        raise OSError("disco cheio")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        fileio.atomic_write(path, b"novo")
    assert path.read_bytes() == b"antigo"
    assert [p.name for p in tmp_path.iterdir()] == ["a.cadinho"]


def test_recovery_cycle(tmp_path):
    assert fileio.read_recovery() is None
    fileio.write_recovery(drawing(), str(tmp_path / "garagem.cadinho"))
    doc, original, when = fileio.read_recovery()
    assert doc.title == "Garagem"
    assert original.endswith("garagem.cadinho")
    assert when > 0
    fileio.clear_recovery()
    assert fileio.read_recovery() is None
    fileio.write_recovery(drawing(), None)
    assert fileio.read_recovery()[1] is None


def test_broken_recovery_is_discarded():
    fileio.recovery_path().parent.mkdir(parents=True, exist_ok=True)
    fileio.recovery_path().write_text("quebrado", encoding="utf-8")
    assert fileio.read_recovery() is None
    assert not fileio.recovery_path().exists()
