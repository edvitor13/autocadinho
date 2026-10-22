import math

import pytest

from autocadinho import geometry as geo


def test_dist_mid_unit():
    assert geo.dist((0, 0), (3, 4)) == 5
    assert geo.mid((0, 0), (10, -4)) == (5, -2)
    assert geo.unit((0, 0), (0, 0)) == (1.0, 0.0)
    ux, uy = geo.unit((1, 1), (1, 6))
    assert (ux, uy) == (0.0, 1.0)


def test_closest_on_segment_clamps_to_ends():
    assert geo.closest_on_segment((5, 5), (0, 0), (10, 0)) == (5, 0)
    assert geo.closest_on_segment((-5, 3), (0, 0), (10, 0)) == (0, 0)
    assert geo.closest_on_segment((50, 3), (0, 0), (10, 0)) == (10, 0)
    assert geo.closest_on_segment((3, 3), (2, 2), (2, 2)) == (2, 2)


def test_ortho_picks_nearest_axis():
    assert geo.ortho((0, 0), (100, 20)) == (100, 0)
    assert geo.ortho((0, 0), (20, -100)) == (0, -100)


def test_snap_grid_and_values():
    assert geo.snap_value(14, 10) == 10
    assert geo.snap_value(15.1, 10) == 20
    assert geo.snap_value(7.3, 0) == 7.3
    assert geo.snap_grid((-4, 26), 10) == (0.0, 30.0)
    assert math.copysign(1, geo.snap_value(-1, 10)) == 1  # sem -0.0


def test_rotate90_clockwise_on_screen():
    assert geo.rotate90((10, 0), (0, 0)) == (0, 10)
    assert geo.rotate90((0, 10), (0, 0)) == (-10, 0)
    assert geo.rotate90((5, 5), (5, 5)) == (5, 5)


def test_normal_up_points_up_or_left():
    assert geo.normal_up((0, 0), (10, 0)) == (0.0, -1.0)
    assert geo.normal_up((10, 0), (0, 0)) == (0.0, -1.0)
    assert geo.normal_up((0, 0), (0, 10)) == (-1.0, 0.0)
    assert geo.normal_up((0, 10), (0, 0)) == (-1.0, 0.0)


@pytest.mark.parametrize("a,b,expected", [
    ((0, 0), (10, 0), 0.0),
    ((10, 0), (0, 0), 0.0),
    ((0, 0), (0, 10), -90.0),
    ((0, 10), (0, 0), -90.0),
    ((0, 0), (10, 10), 45.0),
])
def test_readable_angle_never_upside_down(a, b, expected):
    assert geo.readable_angle(a, b) == pytest.approx(expected)


def test_rect_norm_and_intersections():
    assert geo.rect_norm(10, 20, 0, 5) == (0, 5, 10, 15)
    assert geo.segments_intersect((0, 0), (10, 10), (0, 10), (10, 0))
    assert not geo.segments_intersect((0, 0), (10, 0), (0, 5), (10, 5))
    assert geo.segments_intersect((0, 0), (10, 0), (10, 0), (20, 0))  # encostam na ponta
    assert geo.segment_touches_rect((-10, 5), (20, 5), (0, 0, 10, 10))
    assert geo.segment_touches_rect((2, 2), (3, 3), (0, 0, 10, 10))
    assert not geo.segment_touches_rect((20, 20), (30, 30), (0, 0, 10, 10))


def test_format_length_units_and_separator():
    assert geo.format_length(350) == "3,50 m"
    assert geo.format_length(350, "m", ".") == "3.50 m"
    assert geo.format_length(350, "cm") == "350 cm"
    assert geo.format_length(12.5, "cm") == "12,5 cm"
    assert geo.format_length(-120) == "1,20 m"


def test_snap_prefers_points_then_lines_then_grid():
    pts = [(100, 0)]
    segs = [((0, 50), (200, 50))]
    s = geo.snap((103, 2), pts, segs, tol=10, step=10)
    assert s == geo.Snap((100.0, 0.0), "point")
    s = geo.snap((63, 47), pts, segs, tol=10, step=10)
    assert s == geo.Snap((60.0, 50.0), "line")  # sobre a linha e na grade ao longo dela
    s = geo.snap((63, 87), pts, segs, tol=10, step=10)
    assert s == geo.Snap((60.0, 90.0), "grid")
    s = geo.snap((63, 87), pts, segs, tol=10, step=10, grid=False)
    assert s == geo.Snap((63, 87), "none")


def test_snap_along_vertical_line_stays_inside_segment():
    s = geo.snap((48, 198), [], [((50, 0), (50, 195))], tol=10, step=10)
    assert s.kind == "line"
    assert s.point == (50.0, 195.0)
