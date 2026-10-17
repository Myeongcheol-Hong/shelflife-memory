import copy
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


def test_each_panel_draws_the_dense_curve_and_every_scheduled_policy(drawn, metrics):
    found, places = metrics["test"]["policies"], metrics["test"]["on the dense curve"]
    bound = [n for n in places if n.startswith("true-rate")]
    assert len(marks(drawn, "circle", "knot")) == 2 * sum(n.startswith("fixed ") for n in found)
    assert len(marks(drawn, "polyline", "curve")) == 2
    # The scheduled policies and the bound in each panel, and one of each in the legend.
    assert len(marks(drawn, "circle", "policy")) == 2 * (len(places) - len(bound)) + 1
    assert len(marks(drawn, "circle", "bound")) == 2 * len(bound) + 1
    # Every read and the oracle, set apart in the left panel only, and the legend's.
    assert len(marks(drawn, "rect", "apart")) == len(figure.APART) + 1


def test_a_policy_not_drawn_or_outside_its_panel_is_refused(metrics):
    extra = copy.deepcopy(metrics)
    extra["test"]["policies"]["something new"] = extra["test"]["policies"]["fixed 30"]
    with pytest.raises(ValueError, match="not drawn: \\['something new'\\]"):
        figure.svg(extra)
    for key, value in [("value", 3.0), ("ci", [0.9, 3.0])]:  # the right panel ends at 2.5
        moved = copy.deepcopy(metrics)
        moved["test"]["policies"]["count-aware μ=4.92"][figure.COST][key] = value
        with pytest.raises(ValueError, match="count-aware .* is outside its panel"):
            figure.svg(moved)
    wide = copy.deepcopy(metrics)  # a gap bar past the right panel's top, 62%
    wide["test"]["on the dense curve"]["count-aware μ=4.92"]["ci"] = [-0.01, 0.3]
    with pytest.raises(ValueError, match="count-aware .* is outside its panel"):
        figure.svg(wide)
    with pytest.raises(ValueError, match="never re-checked .* is outside its panel"):
        figure.svg(metrics, never=0.95)


def test_the_right_panel_labels_each_policy_once(drawn):
    column = figure.ZOOM.x1 + 12
    texts = [t for t in drawn.iter(f"{{{NS['s']}}}text") if float(t.get("x")) == column]
    lines = [line for name in figure.NAMES.values() for line in name.split("\n")]
    assert sorted(t.text for t in texts) == sorted(lines)
    ys = sorted(float(t.get("y")) for t in texts)
    assert all(b - a >= 14 for a, b in zip(ys, ys[1:], strict=False))
    # The tuned point is fixed 30 itself: its two lines sit together.
    (first,) = [float(t.get("y")) for t in texts if t.text == "tuned per-class"]
    assert first + 14 in ys


def test_never_re_checked_is_a_line_with_its_value(drawn, metrics):
    y = round(figure.FULL.y(0.8352), 1)
    (line,) = marks(drawn, "line", "ref")
    assert [float(line.get(k)) for k in ("x1", "y1", "x2", "y2")] == [
        figure.FULL.x0,
        y,
        figure.FULL.x1,
        y,
    ]
    texts = [t.text for t in drawn.iter(f"{{{NS['s']}}}text")]
    assert "never re-checked: 83.5%" in texts
    assert "never re-checked" not in figure.svg(metrics)  # no value, no line


def test_every_read_shows_both_its_rates_and_the_oracle_its_rule(drawn):
    texts = [t.text for t in drawn.iter(f"{{{NS['s']}}}text")]
    assert ["every read", "0% stale answers,", "20.6% stale claim-days"] == [
        t for t in texts if t.startswith(("every read", "0% stale", "20.6%"))
    ]
    assert "oracle: checks each change" in texts


def test_each_policys_bars_are_its_cost_and_its_gap_around_the_curve_drawn(drawn, metrics):
    """The horizontal bar is the cost interval at the policy's staleness. The vertical bar
    is the paired gap interval drawn around the curve's value at that cost, and that value
    is on the line drawn in the right panel, so a bar wholly below the line is a policy
    below the curve. Only the true-rate bound's is."""
    test, z = metrics["test"], figure.ZOOM
    curve = marks(drawn, "polyline", "curve")[1]
    lines = [
        {k: float(b.get(k)) for k in ("x1", "y1", "x2", "y2")}
        for cls in ("bar p", "bar b")
        for b in marks(drawn, "line", cls)
    ]
    places = test["on the dense curve"]
    same = [n for n, place in places.items() if place["ci"] == [0, 0]]
    assert len(same) == 1 and same[0].startswith("per-class tuned")  # = fixed 30, no bars
    assert len(lines) == 2 * (len(places) - 1)
    for name, place in places.items():
        m = test["policies"][name]
        cost, stale = m[figure.COST]["value"], m[figure.STALE]["value"]
        x, y, on_curve = round(z.x(cost), 1), round(z.y(stale), 1), stale - place["value"]
        if name in same:
            assert not [b for b in lines if x in (b["x1"], b["x2"]) or y in (b["y1"], b["y2"])]
            continue
        (cost_bar,) = [b for b in lines if b["y1"] == y == b["y2"] and b["x1"] != b["x2"]]
        assert [cost_bar["x1"], cost_bar["x2"]] == [round(z.x(c), 1) for c in m[figure.COST]["ci"]]
        (gap_bar,) = [b for b in lines if b["x1"] == x == b["x2"]]
        ends = sorted([gap_bar["y1"], gap_bar["y2"]])
        assert ends == pytest.approx(sorted(z.y(on_curve + c) for c in place["ci"]), abs=0.05)
        assert z.y(on_curve) == pytest.approx(_y_at(curve, x), abs=0.5)
        below = ends[0] > _y_at(curve, x)  # less stale is lower on the page
        assert below == name.startswith("true-rate")


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
        ("per-class tuned 30/30/30", "tuned per-class\n= fixed 30 (identical, no bars)"),
        ("per-class, Claude's labels", "per-class, Claude's labels"),
        ("true-rate μ=5.911 (exploratory)", "true-rate bound (exploratory)"),
        ("something new", "something new"),
    ],
)
def test_labels_take_the_first_matching_prefix(name, shown):
    assert figure.label(name) == shown


def test_each_theme_has_its_own_colors_and_no_media_query(metrics):
    light, dark = (figure.svg(metrics, 0.8352, colors) for colors in figure.THEMES.values())
    assert "@media" not in light + dark
    assert "--surface: #fcfcfb" in light and "--surface: #1a1a19" in dark
    assert light.replace(figure.THEMES["pareto.svg"], "") == dark.replace(
        figure.THEMES["pareto-dark.svg"], ""
    )


def test_main_writes_the_committed_figures_again(tmp_path, monkeypatch):
    shutil.copy(RUN / "metrics.json", tmp_path / "metrics.json")
    monkeypatch.setattr(figure, "RUN", tmp_path)
    monkeypatch.chdir(ROOT)  # the M6 run is read from the repository
    assert figure.main() == 0
    for name in ("pareto.svg", "pareto-dark.svg"):
        assert (tmp_path / name).read_text() == (RUN / name).read_text()
