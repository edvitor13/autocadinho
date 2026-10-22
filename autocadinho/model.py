"""Modelo do desenho, sem Qt: os elementos (viga, linha, pilar, formas, texto, medida, símbolos) e o documento.

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
    if isinstance(default, list):
        return _points(value)
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


def _points(value: Any) -> list[list[float]]:
    """Lista de pontos [[x, y], ...] lida do arquivo; pares estranhos ficam de fora."""
    out = []
    for item in value if isinstance(value, list) else []:
        try:
            x, y = float(item[0]), float(item[1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            out.append([x, y])
    return out


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
        if not el.sane():
            raise ValueError(f"elemento sem conserto: {data.get('kind')!r}")
        if not el.id:
            el.id = new_id()
        return el

    def sane(self) -> bool:
        """Ajusta valores impossíveis vindos de um arquivo; False = o elemento não tem como ser usado."""
        return True

    def name_key(self) -> str:
        """Nome do tipo para a interface (traduzir com _() ao mostrar)."""
        return self.title

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
    arrow_start: bool = False  # seta na ponta p1
    arrow_end: bool = False  # seta na ponta p2


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
    show_area: bool = False

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
    font: str = ""  # família da fonte; vazio = a fonte do desenho
    italic: bool = False

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


@_register
@dataclass
class Ellipse(Element):
    """Círculo ou elipse dentro do retângulo x, y, w, h (desenhado de um canto ao outro, como no Paint)."""

    kind: ClassVar[str] = "ellipse"
    title: ClassVar[str] = N_("Círculo")
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 100.0
    width: float = 3.0
    dashed: bool = False
    fill: bool = False
    show_dims: bool = False
    show_area: bool = False

    def is_circle(self) -> bool:
        return abs(self.w - self.h) < 0.05

    def name_key(self) -> str:
        return self.title if self.is_circle() else N_("Elipse")

    def area(self) -> float:
        return math.pi * self.w * self.h / 4

    def center(self) -> Point:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def rotate90(self, center: Point) -> None:
        a = geo.rotate90((self.x, self.y), center)
        b = geo.rotate90((self.x + self.w, self.y + self.h), center)
        self.x, self.y, self.w, self.h = geo.rect_norm(a[0], a[1], b[0], b[1])

    def outline(self) -> list[Point]:
        cx, cy = self.center()
        return geo.ellipse_points(cx, cy, self.w / 2, self.h / 2)

    def key_points(self) -> list[Point]:
        cx, cy = self.center()
        return [(cx, cy), (cx, self.y), (self.x + self.w, cy), (cx, self.y + self.h), (self.x, cy)]

    def snap_segments(self) -> list[Seg]:
        pts = self.outline()
        return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


@_register
@dataclass
class Polygon(Element):
    """Forma de vários lados retos, ponto a ponto (o triângulo é um polígono de 3 pontos)."""

    kind: ClassVar[str] = "poly"
    title: ClassVar[str] = N_("Polígono")
    points: list[list[float]] = field(default_factory=list)
    closed: bool = True  # False = linha com vários pontos, sem fechar
    width: float = 3.0
    dashed: bool = False
    fill: bool = False
    show_lengths: bool = False
    show_area: bool = False

    def sane(self) -> bool:
        return len(self.points) >= 2

    def pts(self) -> list[Point]:
        return [(p[0], p[1]) for p in self.points]

    def name_key(self) -> str:
        if not self.closed:
            return N_("Linha com pontos")
        return N_("Triângulo") if len(self.points) == 3 else self.title

    def sides(self) -> list[Seg]:
        pts = self.pts()
        n = len(pts)
        if n < 2:
            return []
        out = [(pts[i], pts[i + 1]) for i in range(n - 1)]
        if self.closed and n > 2:
            out.append((pts[-1], pts[0]))
        return out

    def area(self) -> float:
        return abs(geo.polygon_area(self.pts())) if self.closed and len(self.points) > 2 else 0.0

    def perimeter(self) -> float:
        return sum(geo.dist(a, b) for a, b in self.sides())

    def center(self) -> Point:
        pts = self.pts()
        if not pts:
            return (0.0, 0.0)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    def move(self, dx: float, dy: float) -> None:
        self.points = [[x + dx, y + dy] for x, y in self.points]

    def rotate90(self, center: Point) -> None:
        self.points = [list(geo.rotate90((x, y), center)) for x, y in self.points]

    def key_points(self) -> list[Point]:
        return self.pts() + [geo.mid(a, b) for a, b in self.sides()]

    def snap_segments(self) -> list[Seg]:
        return [s for s in self.sides() if geo.dist(*s) > 1e-6]


# Símbolos prontos: (nome na interface, largura e comprimento padrão em cm).
SYMBOLS: dict[str, tuple[str, float, float]] = {
    "door": (N_("Porta"), 80.0, 80.0),
    "door2": (N_("Porta dupla"), 160.0, 80.0),
    "sliding": (N_("Porta de correr"), 120.0, 15.0),
    "window": (N_("Janela"), 120.0, 15.0),
    "stairs": (N_("Escada"), 300.0, 100.0),
    "toilet": (N_("Vaso sanitário"), 40.0, 65.0),
    "sink": (N_("Pia"), 50.0, 40.0),
    "shower": (N_("Chuveiro"), 80.0, 80.0),
    "north": (N_("Norte"), 80.0, 80.0),
}
WALL_SYMBOLS = ("door", "door2", "sliding", "window")  # ficam na parede e podem abrir um vão nela
STEP_CM = 28.0  # piso de um degrau, para a escada com degraus automáticos


@_register
@dataclass
class Symbol(Element, Labeled):
    """Símbolo pronto (porta, janela, escada...) desenhado num sistema próprio, girado `angle` graus.

    O ponto x, y é o meio do vão na parede (portas e janelas) ou o centro (os outros). No sistema do
    símbolo, x corre ao longo da parede (ou do comprimento) e y, para dentro do cômodo.
    """

    kind: ClassVar[str] = "symbol"
    title: ClassVar[str] = N_("Símbolo")
    shape: str = "door"
    x: float = 0.0
    y: float = 0.0
    w: float = 80.0
    h: float = 80.0
    angle: float = 0.0
    flip_x: bool = False  # espelhado ao longo da parede (dobradiça do outro lado, escada no outro sentido)
    flip_y: bool = False  # virado para o outro lado da parede (a porta abre para fora)
    wall: float = 0.0  # espessura da parede aberta embaixo de portas e janelas (0 = não abre)
    steps: int = 0  # degraus da escada (0 = automático, um a cada 28 cm)

    def sane(self) -> bool:
        # Símbolo de uma versão mais nova: ignorado, como um tipo desconhecido.
        if self.shape not in SYMBOLS:
            return False
        self.w, self.h = max(self.w, 1.0), max(self.h, 1.0)
        self.wall, self.steps = max(self.wall, 0.0), max(self.steps, 0)
        return True

    def name_key(self) -> str:
        return SYMBOLS.get(self.shape, (self.title,))[0]

    def in_wall(self) -> bool:
        return self.shape in WALL_SYMBOLS

    def thickness(self) -> float:
        """Espessura usada para desenhar janelas e portas de correr (a da parede ou uma padrão)."""
        return self.wall if self.wall > 0 else min(max(self.w * 0.12, 8.0), 30.0)

    def step_count(self) -> int:
        return self.steps if self.steps > 0 else max(2, round(self.w / STEP_CM))

    def local_bounds(self) -> tuple[float, float, float, float]:
        """Retângulo (x0, y0, x1, y1) que o símbolo ocupa no próprio sistema."""
        hw = self.w / 2
        if self.shape == "door":
            return (-hw, -self.wall / 2, hw, self.w)
        if self.shape == "door2":
            return (-hw, -self.wall / 2, hw, hw)
        if self.shape in ("sliding", "window"):
            t = self.thickness() / 2
            return (-hw, -t, hw, t)
        hh = self.h / 2
        if self.shape == "north":
            return (-hw, -hh - min(self.w, self.h) * 0.42, hw, hh)
        return (-hw, -hh, hw, hh)

    def to_world(self, lx: float, ly: float) -> Point:
        if self.flip_x:
            lx = -lx
        if self.flip_y:
            ly = -ly
        a = math.radians(self.angle)
        c, s = math.cos(a), math.sin(a)
        return (self.x + lx * c - ly * s, self.y + lx * s + ly * c)

    def to_local(self, pt: Point) -> Point:
        a = math.radians(self.angle)
        c, s = math.cos(a), math.sin(a)
        dx, dy = pt[0] - self.x, pt[1] - self.y
        lx, ly = dx * c + dy * s, -dx * s + dy * c
        return (-lx if self.flip_x else lx, -ly if self.flip_y else ly)

    def corners(self) -> list[Point]:
        x0, y0, x1, y1 = self.local_bounds()
        return [self.to_world(x0, y0), self.to_world(x1, y0), self.to_world(x1, y1), self.to_world(x0, y1)]

    def label_anchor(self) -> Point:
        return self.center()

    def center(self) -> Point:
        x0, y0, x1, y1 = self.local_bounds()
        return self.to_world((x0 + x1) / 2, (y0 + y1) / 2)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def rotate90(self, center: Point) -> None:
        self.x, self.y = geo.rotate90((self.x, self.y), center)
        self.angle = (self.angle + 90) % 360
        self._rotate_label()

    def key_points(self) -> list[Point]:
        if self.in_wall():
            return [(self.x, self.y), self.to_world(-self.w / 2, 0), self.to_world(self.w / 2, 0)]
        return self.corners() + [self.center()]

    def snap_segments(self) -> list[Seg]:
        if self.in_wall():
            return []
        c = self.corners()
        return [(c[i], c[(i + 1) % 4]) for i in range(4)]


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
    font: str = ""  # fonte dos nomes, das medidas e dos textos sem fonte própria; vazio = a padrão
    # Nomes automáticos: "VIGA" dá VIGA 1, VIGA 2…; "P" dá P1, P2…; vazio = sem nome automático.
    beam_prefix: str = field(default_factory=beam_prefix)
    pillar_prefix: str = field(default_factory=pillar_prefix)
    elements: list[Element] = field(default_factory=list)

    SETTINGS: ClassVar[tuple[str, ...]] = ("unit", "label_size", "beam_width", "pillar_w", "pillar_h", "snap_step",
                                           "beam_prefix", "pillar_prefix", "font")
    PREFIX_MAX = 24
    FONT_MAX = 80
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
        doc.font = doc.font.strip()[:cls.FONT_MAX]
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
