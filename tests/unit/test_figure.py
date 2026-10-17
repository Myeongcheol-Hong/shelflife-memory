import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from eval.replay import figure

ROOT = Path(__file__).parents[2]
RUN = ROOT / figure.RUN
NS = {"s": "http://www.w3.org/2000/svg"}


@pytest.fixture(scope="module")
def metrics():
    return json.loads((RUN / "metrics.json").read_text())


@pytest.fixture(scope="module")
def drawn(metrics):
    return ET.fromstring(figure.svg(metrics, never=0.8352))


def marks(root, tag, cls):
    return [e for e in root.iter(f"{{{NS['s']}}}{tag}") if e.get("class") == cls]


def test_each_panel_draws_the_dense_curve_and_every_scheduled_policy(drawn):
    assert len(marks(drawn, "circle", "knot")) == 2 * 11
    assert len(marks(drawn, "polyline", "curve")) == 2
    # Six scheduled policies and the bound in each panel, and one of each in the legend.
    assert len(marks(drawn, "circle", "policy")) == 2 * 6 + 1
    assert len(marks(drawn, "circle", "bound")) == 2 * 1 + 1
    # Every read and the oracle, set apart in the left panel only, and the legend's.
    assert len(marks(drawn, "rect", "apart")) == 2 + 1


def test_the_right_panel_labels_each_policy_once(drawn):
    column = figure.ZOOM.x1 + 12
    names = [t.text for t in drawn.iter(f"{{{NS['s']}}}text") if float(t.get("x")) == column]
    assert sorted(names) == sorted(figure.NAMES.values())
    ys = [float(t.get("y")) for t in drawn.iter(f"{{{NS['s']}}}text") if t.text in names]
    assert all(b - a >= 16 for a, b in zip(sorted(ys), sorted(ys)[1:], strict=False))


def test_never_re_checked_is_a_line_with_its_value(drawn, metrics):
    texts = [t.text for t in drawn.iter(f"{{{NS['s']}}}text")]
    assert "never re-checked: 83.5%" in texts
    assert "every read" in texts and "oracle: checks each change" in texts
    assert "never re-checked" not in figure.svg(metrics)  # no value, no line


def test_the_gap_bar_is_centered_on_the_curve_drawn(drawn, metrics):
    """The true-rate bound's paired interval lies below the curve at its cost, and its
    center, the curve's value there, is on the line drawn in the right panel."""
    test = metrics["test"]
    name = next(n for n in test["on the dense curve"] if n.startswith("true-rate"))
    cost, stale = (test["policies"][name][k]["value"] for k in (figure.COST, figure.STALE))
    place = test["on the dense curve"][name]
    x = round(figure.ZOOM.x(cost), 1)
    bars = marks(drawn, "line", "bar b")
    (bar,) = [b for b in bars if float(b.get("x1")) == x == float(b.get("x2"))]
    curve_y = _y_at(marks(drawn, "polyline", "curve")[1], x)
    ends = sorted(float(bar.get(k)) for k in ("y1", "y2"))
    assert ends[0] > curve_y  # below the curve: less stale, lower on the page
    assert ends == pytest.approx(
        sorted(figure.ZOOM.y(stale - place["value"] + c) for c in place["ci"]), abs=0.05
    )
    assert figure.ZOOM.y(stale - place["value"]) == pytest.approx(curve_y, abs=0.5)


def _y_at(polyline, x):
    pts = sorted(tuple(map(float, p.split(","))) for p in polyline.get("points").split())
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    raise AssertionError(f"{x} is not on the curve")


def test_chords_are_linear_in_cost_between_fixed_points():
    pts = figure._chords([(1.0, 0.5), (3.0, 0.3)], steps=4)
    assert pts == [(1.0, 0.5), (1.5, 0.45), (2.0, 0.4), (2.5, 0.35), (3.0, 0.3)]


def test_a_panel_maps_its_ranges_to_its_box():
    p = figure.Panel(0, 100, 10, 110, (0.1, 10), (0, 0.5))
    assert (p.x(0.1), p.x(1), p.x(10)) == pytest.approx((0, 50, 100))
    assert (p.y(0), p.y(0.25), p.y(0.5)) == pytest.approx((110, 60, 10))


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        ("per-class", "per-class (7/30/180 days)"),
        ("per-class tuned 30/30/30", "tuned per-class = fixed 30"),
        ("per-class, Claude's labels", "per-class, Claude's labels"),
        ("true-rate μ=5.911 (exploratory)", "true-rate bound (exploratory)"),
        ("something new", "something new"),
    ],
)
def test_labels_take_the_first_matching_prefix(name, shown):
    assert figure.label(name) == shown


def test_main_writes_the_committed_figure_again(tmp_path, monkeypatch):
    shutil.copy(RUN / "metrics.json", tmp_path / "metrics.json")
    monkeypatch.chdir(ROOT)  # the M6 run is read from the repository
    assert figure.main([str(tmp_path)]) == 0
    assert (tmp_path / "pareto.svg").read_text() == (RUN / "pareto.svg").read_text()
