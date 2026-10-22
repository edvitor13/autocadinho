"""Contas de geometria do desenho, sem Qt.

Tudo em centímetros (cm), com x para a direita e y para baixo, como na tela.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

Point = tuple[float, float]
Seg = tuple[Point, Point]


def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def mid(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def closest_on_segment(p: Point, a: Point, b: Point) -> Point:
    """Ponto do segmento a–b mais perto de p."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 <= 1e-12:
        return a
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2
    t = max(0.0, min(1.0, t))
    return (a[0] + t * dx, a[1] + t * dy)


def dist_to_segment(p: Point, a: Point, b: Point) -> float:
    return dist(p, closest_on_segment(p, a, b))


def ortho(start: Point, p: Point) -> Point:
    """Prende p na horizontal ou na vertical que passa por start (a que estiver mais perto)."""
    dx, dy = p[0] - start[0], p[1] - start[1]
    return (p[0], start[1]) if abs(dx) >= abs(dy) else (start[0], p[1])


def snap_value(v: float, step: float) -> float:
    if step <= 0:
        return v
    return round(v / step) * step + 0.0  # + 0.0 tira o -0.0


def snap_grid(p: Point, step: float) -> Point:
    return (snap_value(p[0], step), snap_value(p[1], step))


def rotate90(p: Point, center: Point) -> Point:
    """Gira p 90° no sentido horário (na tela, com y para baixo) em volta de center."""
    dx, dy = p[0] - center[0], p[1] - center[1]
    return (center[0] - dy, center[1] + dx)


def unit(a: Point, b: Point) -> Point:
    """Direção unitária de a para b ((1, 0) se os pontos coincidem)."""
    d = dist(a, b)
    if d < 1e-9:
        return (1.0, 0.0)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def normal_up(a: Point, b: Point) -> Point:
    """Normal unitária do segmento que aponta para cima (ou para a esquerda, se ele for vertical)."""
    ux, uy = unit(a, b)
    nx, ny = uy, -ux
    if ny > 1e-9 or (abs(ny) <= 1e-9 and nx > 0):
        nx, ny = -nx, -ny
    return (nx + 0.0, ny + 0.0)


def readable_angle(a: Point, b: Point) -> float:
    """Ângulo (graus) para escrever ao longo de a–b sem o texto ficar de cabeça para baixo.

    Fica em [-90, 90): na vertical o texto é lido de baixo para cima (-90°).
    """
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    if ang >= 90 - 1e-9:
        ang -= 180
    elif ang < -90 - 1e-9:
        ang += 180
    return ang


def text_up(angle: float) -> Point:
    """Direção "para cima" de um texto girado `angle` graus (rotação do QPainter)."""
    r = math.radians(angle)
    return (math.sin(r), -math.cos(r))


def rect_norm(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float, float, float]:
    """(x, y, largura, altura) com largura e altura positivas."""
    return (min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_seg(a: Point, b: Point, c: Point) -> bool:
    return min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9 and \
        min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return True
    return (abs(d1) < 1e-9 and _on_seg(p3, p4, p1)) or (abs(d2) < 1e-9 and _on_seg(p3, p4, p2)) or \
        (abs(d3) < 1e-9 and _on_seg(p1, p2, p3)) or (abs(d4) < 1e-9 and _on_seg(p1, p2, p4))


def segment_touches_rect(a: Point, b: Point, rect: tuple[float, float, float, float]) -> bool:
    """O segmento a–b encosta no retângulo (x0, y0, x1, y1)?"""
    x0, y0, x1, y1 = rect
    for p in (a, b):
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return True
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return any(segments_intersect(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def format_length(cm: float, unit: str = "m", sep: str = ",") -> str:
    """Medida para mostrar: "3,50 m" ou "350 cm" (com o separador decimal do idioma)."""
    cm = abs(cm)
    if unit == "cm":
        v = round(cm, 1)
        txt = f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}"
        return txt.replace(".", sep) + " cm"
    return f"{cm / 100:.2f}".replace(".", sep) + " m"


@dataclass(frozen=True)
class Snap:
    """Resultado do encaixe: o ponto e o tipo ("point" = ponta/meio/canto, "line", "grid", "none")."""

    point: Point
    kind: str


def snap(p: Point, points: Iterable[Point], segments: Iterable[Seg], tol: float, step: float,
         grid: bool = True) -> Snap:
    """Encaixa p: primeiro em pontos (pontas, meios, cantos), depois sobre linhas, depois na grade.

    `tol` é a distância máxima (cm) para os encaixes em objetos; `step` é o passo da grade (cm).
    Sobre uma linha reta (horizontal ou vertical), a posição ao longo dela também segue a grade.
    """
    best: Point | None = None
    bd = tol
    for q in points:
        d = dist(p, q)
        if d <= bd:
            best, bd = q, d
    if best is not None:
        return Snap((best[0] + 0.0, best[1] + 0.0), "point")
    best_seg: Seg | None = None
    bd = tol
    for a, b in segments:
        c = closest_on_segment(p, a, b)
        d = dist(p, c)
        if d <= bd:
            best, bd, best_seg = c, d, (a, b)
    if best is not None and best_seg is not None:
        (ax, ay), (bx, by) = best_seg
        if grid and step > 0:
            if abs(ay - by) < 1e-6:
                x = min(max(snap_value(best[0], step), min(ax, bx)), max(ax, bx))
                best = (x, ay)
            elif abs(ax - bx) < 1e-6:
                y = min(max(snap_value(best[1], step), min(ay, by)), max(ay, by))
                best = (ax, y)
        return Snap((best[0] + 0.0, best[1] + 0.0), "line")
    if grid and step > 0:
        return Snap(snap_grid(p, step), "grid")
    return Snap(p, "none")
