"""Arquivos .cadinho (JSON), gravação segura e a cópia de recuperação.

A gravação nunca deixa um arquivo pela metade: escreve num temporário ao lado e só troca no fim.
A cópia de recuperação é gravada de tempos em tempos enquanto há mudanças não salvas e é apagada
quando o desenho é salvo ou o app fecha normalmente. Se o computador desligar (queda de energia),
o app oferece recuperar o desenho na próxima vez que abrir.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from . import FILE_EXT, __version__
from .model import Document

RECOVERY_NAME = "recuperacao" + FILE_EXT


class FileError(Exception):
    """Erro ao ler ou gravar um desenho (mensagem pronta para mostrar)."""


def atomic_write(path: str | os.PathLike, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def encode(doc: Document, thumbnail_png: bytes | None = None, extra: dict | None = None) -> bytes:
    data = doc.to_dict()
    data["version"] = __version__
    if extra:
        data.update(extra)
    if thumbnail_png:
        data["thumbnail"] = base64.b64encode(thumbnail_png).decode("ascii")
    return json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")


def save(doc: Document, path: str | os.PathLike, thumbnail_png: bytes | None = None) -> None:
    try:
        atomic_write(path, encode(doc, thumbnail_png))
    except OSError as exc:
        raise FileError(str(exc)) from exc


def _read_json(path: str | os.PathLike) -> dict:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise FileError(str(exc)) from exc
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise FileError("not-a-drawing") from exc
    if not isinstance(data, dict) or "elements" not in data:
        raise FileError("not-a-drawing")
    return data


def load(path: str | os.PathLike) -> Document:
    data = _read_json(path)
    try:
        return Document.from_dict(data)
    except ValueError as exc:
        raise FileError("not-a-drawing") from exc


def read_thumbnail(path: str | os.PathLike) -> bytes | None:
    try:
        data = _read_json(path)
        thumb = data.get("thumbnail")
        return base64.b64decode(thumb) if isinstance(thumb, str) else None
    except (FileError, ValueError):
        return None


# ------------------------------------------------------------------------------- recuperação
def data_dir() -> Path:
    """Pasta de dados do app (AUTOCADINHO_DATA_DIR em testes)."""
    env = os.environ.get("AUTOCADINHO_DATA_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return Path(base) / "Autocadinho"
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "autocadinho"


def recovery_path() -> Path:
    return data_dir() / RECOVERY_NAME


def write_recovery(doc: Document, original: str | None) -> None:
    extra = {"recovery": {"original": original or "", "time": time.time()}}
    try:
        atomic_write(recovery_path(), encode(doc, extra=extra))
    except OSError:
        pass  # recuperação é só uma rede de segurança


def read_recovery() -> tuple[Document, str | None, float] | None:
    """(desenho, caminho original ou None, hora em que foi gravado) ou None."""
    path = recovery_path()
    if not path.exists():
        return None
    try:
        data = _read_json(path)
        doc = Document.from_dict(data)
    except (FileError, ValueError):
        clear_recovery()
        return None
    info = data.get("recovery") or {}
    original = str(info.get("original") or "") or None
    when = float(info.get("time") or path.stat().st_mtime)
    return doc, original, when


def clear_recovery() -> None:
    try:
        recovery_path().unlink()
    except OSError:
        pass
