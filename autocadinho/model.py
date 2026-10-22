"""Modelo do desenho, sem Qt: os elementos (viga, linha, pilar, retângulo, texto, medida) e o documento.

Unidade: centímetros, com y para baixo. Cor vazia ("") quer dizer "tinta": preto no papel e claro no
tema escuro. O documento vira um dicionário JSON (`to_dict`/`from_dict`); o formato de arquivo está
descrito em docs/FORMATO.md.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import MISSING, asdict, dataclass, field, fields
from typing import Any, ClassVar

from . import geometry as geo
from .geometry import Point, Seg
from .i18n import N_, _

FORMAT = 1
KINDS: dict[str, type["Element"]] = {}

# Campos que aceitam None (rótulo em posição automática).
_OPTIONAL = {"label_dx", "label_dy"}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _register(cls):
    KINDS[cls.kind] = cls
    return cls


def _coerce(name: str, default: Any, value: Any) -> Any:
    """Converte um valor lido do arquivo para o tipo do campo; valor estranho vira o padrão."""
    if name in _OPTIONAL:
        if value is None:
            return None
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None
    try:
        if isinstance(default, bool):
            return bool(value)
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            v = float(value)
            return v if math.isfinite(v) else default
        if isinstance(default, str):
            return str(value)
    except (TypeError, ValueError):
        return default
    return value


def _default(f) -> Any:
    if f.default is not MISSING:
        return f.default
    if f.default_factory is not MISSING:
        return f.default_factory()
    return None


@dataclass
class Element:
    kind: ClassVar[str] = ""
    title: ClassVar[str] = ""  # nome para a interface (traduzir com _() ao mostrar)

    id: str = field(default_factory=new_id)
    color: str = ""

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"kind": self.kind}
        d.update(asdict(self))
        return d

    @staticmethod
    def from_dict(data: dict) -> "Element":
        cls = KINDS.get(str(data.get("kind", "")))
        if cls is None:
            raise ValueError(f"tipo de elemento desconhecido: {data.get('kind')!r}")
        kwargs = {}
        for f in fields(cls):
            if f.name in data:
                kwargs[f.name] = _coerce(f.name, _default(f), data[f.name])
        el = cls(**kwargs)
        if not el.id:
            el.id = new_id()
        return el

    def clone(self, new: bool = True) -> "Element":
        el = Element.from_dict(self.to_dict())
        if new:
            el.id = new_id()
        return el

    # geometria ------------------------------------------------------------------------------
    def move(self, dx: float, dy: float) -> None:
        raise NotImplementedError

    def rotate90(self, center: Point) -> None:
        raise NotImplementedError

    def key_points(self) -> list[Point]:
        """Pontos em que outros desenhos encaixam (pontas, meios, cantos, centro)."""
        return []

    def snap_segments(self) -> list[Seg]:
        """Trechos retos sobre os quais outros desenhos encaixam."""
        return []

    def center(self) -> Point:
        raise NotImplementedError


@dataclass
class Labeled:
    """Nome que acompanha o elemento ("VIGA 1", "P3"). Sem posição gravada, ele se posiciona sozinho."""

    label: str = ""
    label_visible: bool = True
    label_dx: float | None = None
    label_dy: float | None = None
    label_rot: int = 0  # 0 = deitado, 90 = em pé (lido de baixo para cima)

    def label_anchor(self) -> Point:
        raise NotImplementedError

    def _rotate_label(self) -> None:
        if self.label_dx is not None and self.label_dy is not None:
            self.label_dx, self.label_dy = -self.label_dy, self.label_dx


@dataclass
class Segment(Element):
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    width: float = 3.0
    show_length: bool = False

    @property
    def p1(self) -> Point:
        return (self.x1, self.y1)

    @property
    def p2(self) -> Point:
        return (self.x2, self.y2)

    def set_points(self, p1: Point, p2: Point) -> None:
        self.x1, self.y1 = p1
        self.x2, self.y2 = p2

    def length(self) -> float:
        return geo.dist(self.p1, self.p2)

    def set_length(self, length: float) -> None:
        """Muda o comprimento mantendo o começo e a direção."""
        ux, uy = geo.unit(self.p1, self.p2)
        self.x2 = self.x1 + ux * length
        self.y2 = self.y1 + uy * length

    def move(self, dx: float, dy: float) -> None:
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def rotate90(self, center: Point) -> None:
        self.set_points(geo.rotate90(self.p1, center), geo.rotate90(self.p2, center))

    def key_points(self) -> list[Point]:
        return [self.p1, self.p2, geo.mid(self.p1, self.p2)]

    def snap_segments(self) -> list[Seg]:
        return [(self.p1, self.p2)] if self.length() > 1e-6 else []

    def center(self) -> Point:
        return geo.mid(self.p1, self.p2)


@_register
@dataclass
class Beam(Segment, Labeled):
    kind: ClassVar[str] = "beam"
    title: ClassVar[str] = N_("Viga")
    width: float = 15.0

    def label_anchor(self) -> Point:
        return self.center()

    def rotate90(self, center: Point) -> None:
        super().rotate90(center)
        self._rotate_label()


@_register
@dataclass
class Line(Segment):
    kind: ClassVar[str] = "line"
    title: ClassVar[str] = N_("Linha")
    dashed: bool = False


@_register
@dataclass
class Pillar(Element, Labeled):
    kind: ClassVar[str] = "pillar"
    title: ClassVar[str] = N_("Pilar")
    x: float = 0.0
    y: float = 0.0
    w: float = 40.0
    h: float = 20.0

    def label_anchor(self) -> Point:
        return (self.x, self.y)

    def center(self) -> Point:
        return (self.x, self.y)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def turn(self) -> None:
        """Gira o pilar 90° no lugar (troca largura e comprimento)."""
        self.w, self.h = self.h, self.w

    def rotate90(self, center: Point) -> None:
        self.x, self.y = geo.rotate90((self.x, self.y), center)
        self.turn()
        self._rotate_label()

    def key_points(self) -> list[Point]:
        return [(self.x, self.y)]


@_register
@dataclass
class Rect(Element):
    kind: ClassVar[str] = "rect"
    title: ClassVar[str] = N_("Retângulo")
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 100.0
    width: float = 3.0
    dashed: bool = False
    fill: bool = False
    show_dims: bool = False

    def corners(self) -> list[Point]:
        return [(self.x, self.y), (self.x + self.w, self.y), (self.x + self.w, self.y + self.h),
                (self.x, self.y + self.h)]

    def center(self) -> Point:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def rotate90(self, center: Point) -> None:
        a = geo.rotate90((self.x, self.y), center)
        b = geo.rotate90((self.x + self.w, self.y + self.h), center)
        self.x, self.y, self.w, self.h = geo.rect_norm(a[0], a[1], b[0], b[1])

    def key_points(self) -> list[Point]:
        c = self.corners()
        return c + [geo.mid(c[i], c[(i + 1) % 4]) for i in range(4)]

    def snap_segments(self) -> list[Seg]:
        c = self.corners()
        return [(c[i], c[(i + 1) % 4]) for i in range(4)]


@_register
@dataclass
class Text(Element):
    kind: ClassVar[str] = "text"
    title: ClassVar[str] = N_("Texto")
    x: float = 0.0
    y: float = 0.0
    text: str = ""
    size: float = 25.0
    bold: bool = False
    rot: int = 0  # 0 = deitado, 90 = em pé (lido de baixo para cima)

    def center(self) -> Point:
        return (self.x, self.y)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def rotate90(self, center: Point) -> None:
        self.x, self.y = geo.rotate90((self.x, self.y), center)
        self.rot = 0 if self.rot else 90


@_register
@dataclass
class Dimension(Element):
    """Medida (cota): mede de p1 a p2 e desenha a linha de cota afastada `offset` cm para o lado."""

    kind: ClassVar[str] = "dim"
    title: ClassVar[str] = N_("Medida")
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    offset: float = 60.0
    text: str = ""  # vazio = a medida calculada

    @property
    def p1(self) -> Point:
        return (self.x1, self.y1)

    @property
    def p2(self) -> Point:
        return (self.x2, self.y2)

    def length(self) -> float:
        return geo.dist(self.p1, self.p2)

    def normal(self) -> Point:
        """Lado para onde `offset` positivo afasta a linha de cota (à esquerda de p1 → p2)."""
        ux, uy = geo.unit(self.p1, self.p2)
        return (uy, -ux)

    def center(self) -> Point:
        return geo.mid(self.p1, self.p2)

    def move(self, dx: float, dy: float) -> None:
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def rotate90(self, center: Point) -> None:
        self.x1, self.y1 = geo.rotate90(self.p1, center)
        self.x2, self.y2 = geo.rotate90(self.p2, center)


def beam_prefix() -> str:
    """Prefixo padrão do nome automático das vigas, no idioma do app."""
    return _("VIGA")


def pillar_prefix() -> str:
    """Prefixo padrão do nome automático dos pilares, no idioma do app."""
    return _("P")


@dataclass
class Document:
    """O desenho: elementos (do fundo para a frente) e ajustes do desenho."""

    title: str = ""
    unit: str = "m"  # "m" ou "cm" nas medidas
    label_size: float = 25.0  # altura das letras dos nomes e das medidas (cm)
    beam_width: float = 15.0  # largura das vigas novas (cm)
    pillar_w: float = 40.0  # tamanho dos pilares novos (cm)
    pillar_h: float = 20.0
    snap_step: float = 10.0  # passo da grade de encaixe (cm)
    # Nomes automáticos: "VIGA" dá VIGA 1, VIGA 2…; "P" dá P1, P2…; vazio = sem nome automático.
    beam_prefix: str = field(default_factory=beam_prefix)
    pillar_prefix: str = field(default_factory=pillar_prefix)
    elements: list[Element] = field(default_factory=list)

    SETTINGS: ClassVar[tuple[str, ...]] = ("unit", "label_size", "beam_width", "pillar_w", "pillar_h", "snap_step",
                                           "beam_prefix", "pillar_prefix")
    PREFIX_MAX = 24
    LIMITS: ClassVar[dict[str, tuple[float, float]]] = {
        "label_size": (2.0, 500.0), "beam_width": (1.0, 200.0), "pillar_w": (1.0, 500.0),
        "pillar_h": (1.0, 500.0), "snap_step": (0.0, 500.0),
    }

    # arquivo --------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "app": "Autocadinho",
            "format": FORMAT,
            "title": self.title,
            "settings": {k: getattr(self, k) for k in self.SETTINGS},
            "elements": [el.to_dict() for el in self.elements],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        if not isinstance(data, dict):
            raise ValueError("o arquivo não tem um desenho")
        doc = cls(title=str(data.get("title", "") or ""))
        settings = data.get("settings") or {}
        if isinstance(settings, dict):
            for k in cls.SETTINGS:
                if k in settings:
                    setattr(doc, k, _coerce(k, getattr(doc, k), settings[k]))
        if doc.unit not in ("m", "cm"):
            doc.unit = "m"
        for k, (lo, hi) in cls.LIMITS.items():
            setattr(doc, k, min(max(getattr(doc, k), lo), hi))
        doc.beam_prefix = doc.beam_prefix.strip()[:cls.PREFIX_MAX]
        doc.pillar_prefix = doc.pillar_prefix.strip()[:cls.PREFIX_MAX]
        seen: set[str] = set()
        for item in data.get("elements") or []:
            if not isinstance(item, dict):
                continue
            try:
                el = Element.from_dict(item)
            except ValueError:
                continue  # tipo de uma versão mais nova: ignora
            if el.id in seen:
                el.id = new_id()
            seen.add(el.id)
            doc.elements.append(el)
        return doc

    def copy(self) -> "Document":
        return Document.from_dict(self.to_dict())

    # elementos ------------------------------------------------------------------------------
    def get(self, el_id: str) -> Element | None:
        for el in self.elements:
            if el.id == el_id:
                return el
        return None

    def add(self, el: Element) -> Element:
        self.elements.append(el)
        return el

    def remove(self, ids) -> int:
        ids = set(ids)
        before = len(self.elements)
        self.elements = [el for el in self.elements if el.id not in ids]
        return before - len(self.elements)

    def bring_front(self, ids) -> None:
        ids = set(ids)
        self.elements = [e for e in self.elements if e.id not in ids] + [e for e in self.elements if e.id in ids]

    def send_back(self, ids) -> None:
        ids = set(ids)
        self.elements = [e for e in self.elements if e.id in ids] + [e for e in self.elements if e.id not in ids]

    def next_label(self, prefix: str) -> str:
        """Próximo nome livre: "VIGA 3" (prefixo longo, com espaço) ou "P4" (prefixo curto). Sem prefixo, ""."""
        prefix = prefix.strip()
        if not prefix:
            return ""
        pat = re.compile(rf"^\s*{re.escape(prefix)}\s*(\d+)\s*$", re.IGNORECASE)
        n = 0
        for el in self.elements:
            m = pat.match(getattr(el, "label", "") or "")
            if m:
                n = max(n, int(m.group(1)))
        return f"{prefix} {n + 1}" if len(prefix) > 1 else f"{prefix}{n + 1}"

    def count(self, kind: str) -> int:
        return sum(1 for el in self.elements if el.kind == kind)


def selection_center(elements: list[Element]) -> Point:
    """Centro do retângulo que envolve os centros dos elementos (para girar uma seleção)."""
    pts = [el.center() for el in elements]
    if not pts:
        return (0.0, 0.0)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
