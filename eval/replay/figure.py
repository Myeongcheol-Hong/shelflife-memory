"""The Pareto figure (M7, D12): stale claim-days against checks per claim-month on test,
from M7e's run of every policy, written as an SVG with the standard library.

    uv run python -m eval.replay.figure   # writes pareto.svg into M7e's run folder

Left: the dense fixed-N curve, every policy, never re-checked (M6's run, the same
claims), every read and the oracle set apart. Right: the scheduled policies near fixed
30, each with two 95% intervals: its cost, and its gap to the curve at that cost
(paired over projects, the interval M7e's criterion reads).
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

RUN = Path("eval/results/2026-10-16-45ee09a-compare")
NEVER = Path("eval/results/2026-10-14-369cb77/metrics.json")  # M6: the same claims
COST, STALE, ANSWERS = "checks per claim-month", "stale claim-days", "stale-answer rate"
# Curve labels, offset from the point; a negative dx puts the label to the left.
CURVE_LABELS = {
    "fixed 180": (5, -5),
    "fixed 60": (5, -5),
    "fixed 30": (5, -5),
    "fixed 14": (5, -5),
    "fixed 7": (-5, 15),
    "fixed 3": (-5, -5),
}
NAMES = {  # name prefix in metrics.json: label on the figure
    "per-class tuned": "tuned per-class = fixed 30",
    "per-class, Claude's labels": "per-class, Claude's labels",
    "per-class": "per-class (7/30/180 days)",
    "adaptive": "adaptive (M7b)",
    "budget-aware": "budget-aware (M7d)",
    "count-aware": "count-aware",
    "true-rate": "true-rate bound (exploratory)",
}
STYLE = """
.viz { --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --grid: #e4e3df;
  --policy: #2a78d6; --bound: #eb6834; font: 12px system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { .viz { --surface: #1a1a19; --ink: #f0efec;
  --ink-2: #c3c2b7; --grid: #3a3936; --policy: #3987e5; --bound: #d95926; } }
.bg { fill: var(--surface); } text { fill: var(--ink); } .muted { fill: var(--ink-2); }
.grid { stroke: var(--grid); } .axis { stroke: var(--ink-2); }
.curve { fill: none; stroke: var(--ink-2); stroke-width: 2; } .knot { fill: var(--ink-2); }
.policy { fill: var(--policy); stroke: var(--surface); stroke-width: 2; }
.bound { fill: var(--surface); stroke: var(--bound); stroke-width: 2; }
.bar { stroke: var(--policy); stroke-width: 1.5; } .bar.b { stroke: var(--bound); }
.apart { fill: var(--surface); stroke: var(--ink-2); stroke-width: 2; }
.ref { stroke: var(--ink-2); stroke-dasharray: 4 3; } .lead { stroke: var(--grid); }
"""


@dataclass(frozen=True)
class Panel:
    x0: float
    x1: float
    y0: float  # top
    y1: float  # bottom
    xs: tuple[float, float]  # checks per claim-month, log scale
    ys: tuple[float, float]  # stale claim-days

    def x(self, v: float) -> float:
        lo, hi = map(math.log10, self.xs)
        return self.x0 + (math.log10(v) - lo) / (hi - lo) * (self.x1 - self.x0)

    def y(self, v: float) -> float:
        return self.y1 - (v - self.ys[0]) / (self.ys[1] - self.ys[0]) * (self.y1 - self.y0)


FULL = Panel(70, 430, 70, 380, (0.08, 12), (0, 0.9))
ZOOM = Panel(530, 770, 70, 380, (0.5, 2.5), (0.28, 0.62))


def label(name: str) -> str:
    return next((v for k, v in NAMES.items() if name.startswith(k)), name)


def svg(metrics: dict, never: float | None = None) -> str:
    test = metrics["test"]
    found, places = test["policies"], test["on the dense curve"]
    point = {n: (m[COST]["value"], m[STALE]["value"]) for n, m in found.items()}
    curve = sorted(point[n] for n in found if n.startswith("fixed "))
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" class="viz" viewBox="0 0 1000 470"'
        ' width="1000" height="470" role="img" aria-label="Pareto figure">',
        f"<style>{STYLE}</style>",
        '<rect class="bg" width="1000" height="470"/>',
        _text(500, 28, "Stale claim-days against checks per claim-month, test split", "middle"),
    ]
    for p, title in ((FULL, "Every policy"), (ZOOM, "Scheduled policies near fixed 30")):
        out += _axes(p, title)
        out.append(f'<g clip-path="url(#c{p.x0})">')
        out.append(_poly(p, _chords(curve)))
        out += [_dot(p, x, y, 2.5, "knot") for x, y in curve]
        if p is FULL:
            out += _full_extras(p, point, never)
        for n in places:
            out += _point(p, n, point[n], found[n], places[n], bars=p is ZOOM)
        out.append("</g>")
    out += _apart(FULL, found)  # unclipped: the oracle sits on the axis
    out += _labels(ZOOM, {n: point[n] for n in places})
    out += _legend()
    return "\n".join([*out, "</svg>"]) + "\n"


def _axes(p: Panel, title: str) -> list[str]:
    out = [
        f'<clipPath id="c{p.x0}"><rect x="{p.x0}" y="{p.y0}" width="{p.x1 - p.x0}"'
        f' height="{p.y1 - p.y0}"/></clipPath>',
        _text(p.x0, p.y0 - 12, title),
    ]
    step = 0.2 if p is FULL else 0.1
    for k in range(math.ceil(p.ys[0] / step), int(p.ys[1] / step + 1e-9) + 1):
        y = p.y(k * step)
        out += [_line(p.x0, y, p.x1, y, "grid"), _text(p.x0 - 6, y + 4, f"{k * step:.0%}", "end")]
    for v in (0.1, 0.3, 1, 3, 10) if p is FULL else (0.5, 0.7, 1, 1.5, 2):
        out.append(_text(p.x(v), p.y1 + 16, f"{v:g}", "middle"))
    out += [_line(p.x0, p.y1, p.x1, p.y1, "axis"), _line(p.x0, p.y0, p.x0, p.y1, "axis")]
    out.append(_text((p.x0 + p.x1) / 2, p.y1 + 34, "checks per claim-month (log)", "middle"))
    return out


def _full_extras(p: Panel, point: dict, never: float | None) -> list[str]:
    out = [  # fixed 3 sits at the right edge, so its label goes left
        _text(p.x(c) + dx, p.y(s) + dy, n.split()[1] + " d", "end" if dx < 0 else "start", "muted")
        for n, (dx, dy) in CURVE_LABELS.items()
        for c, s in [point[n]]
    ]
    if never is not None:  # no checks: no place on a log axis, so a line
        out += [
            _line(p.x0, p.y(never), p.x1, p.y(never), "ref"),
            _text(p.x1 - 4, p.y(never) - 6, f"never re-checked: {never:.1%}", "end"),
        ]
    z = ZOOM  # where the right panel looks
    out.append(
        f'<rect class="ref" fill="none" x="{p.x(z.xs[0]):.1f}" y="{p.y(z.ys[1]):.1f}"'
        f' width="{p.x(z.xs[1]) - p.x(z.xs[0]):.1f}"'
        f' height="{p.y(z.ys[0]) - p.y(z.ys[1]):.1f}"/>'
    )
    return out


def _apart(p: Panel, found: dict) -> list[str]:
    """Every read, labeled to its right and upward (clear of the curve) with both its
    rates, since its stale claim-days (between reads) put it above the curve while it
    gives no stale answers; the oracle, on the axis, labeled above."""
    out = []
    for n in ("every read", "oracle"):
        m = found[n]
        x, y = p.x(m[COST]["value"]), p.y(m[STALE]["value"])
        out.append(f'<rect class="apart" x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8"/>')
        if n == "oracle":
            out.append(_text(x, y - 10, "oracle: checks each change", "middle", "muted"))
            continue
        lines = (
            "every read",
            f"{m[ANSWERS]['value']:.0%} stale answers,",
            f"{m[STALE]['value']:.1%} stale claim-days",
        )
        out += [_text(x + 8, y - 24 + 14 * i, s, cls="muted") for i, s in enumerate(lines)]
    return out


def _point(p: Panel, name: str, xy, m: dict, place: dict, bars: bool) -> list[str]:
    cls = "bound" if name.startswith("true-rate") else "policy"
    out = []
    if bars:  # cost interval; gap interval around the curve's value at that cost
        (lo, hi), y = m[COST]["ci"], p.y(xy[1])
        out.append(_line(p.x(lo), y, p.x(hi), y, f"bar {cls[0]}"))
        if place["ci"]:
            line = xy[1] - place["value"]
            out.append(
                _line(
                    p.x(xy[0]),
                    p.y(line + place["ci"][0]),
                    p.x(xy[0]),
                    p.y(line + place["ci"][1]),
                    f"bar {cls[0]}",
                )
            )
    return [*out, _dot(p, *xy, 5, cls)]


def _labels(p: Panel, points: dict) -> list[str]:
    """Direct labels in a column right of the panel, in the points' order, 16px apart."""
    out, last = [], -math.inf
    for n, (x, y) in sorted(points.items(), key=lambda kv: -kv[1][1]):
        at = max(p.y(y), last + 16)
        last = at
        out += [_line(p.x(x) + 6, p.y(y), p.x1 + 8, at - 4, "lead"), _text(p.x1 + 12, at, label(n))]
    return out


def _legend() -> list[str]:
    y = 440
    return [
        _line(70, y - 4, 92, y - 4, "curve"),
        _text(98, y, "fixed N days (the curve)"),
        f'<circle class="policy" cx="270" cy="{y - 4}" r="5"/>',
        _text(280, y, "scheduled policy"),
        f'<circle class="bound" cx="410" cy="{y - 4}" r="5"/>',
        _text(420, y, "true-rate bound: knows the future, exploratory"),
        f'<rect class="apart" x="740" y="{y - 8}" width="8" height="8"/>',
        _text(754, y, "not scheduled (set apart)"),
        _text(
            70,
            y + 20,
            "Bars (right): 95% intervals over projects for the cost and for the"
            " gap to the curve at that cost. M7e's run, 5 seeds, 1 question a week.",
            cls="muted",
        ),
    ]


def _chords(curve: list[tuple[float, float]], steps: int = 8) -> list[tuple[float, float]]:
    """The curve as place() reads it: linear in cost between fixed N (D12), so each
    segment bends a little on the log axis, and a gap bar is centered on the line drawn."""
    out = curve[:1]
    for (c0, s0), (c1, s1) in zip(curve, curve[1:], strict=False):
        ts = (t / steps for t in range(1, steps + 1))
        out += [(c0 + (c1 - c0) * t, s0 + (s1 - s0) * t) for t in ts]
    return out


def _poly(p: Panel, pts) -> str:
    return (
        '<polyline class="curve" points="'
        + " ".join(f"{p.x(x):.1f},{p.y(y):.1f}" for x, y in pts)
        + '"/>'
    )


def _dot(p: Panel, x: float, y: float, r: float, cls: str) -> str:
    return f'<circle class="{cls}" cx="{p.x(x):.1f}" cy="{p.y(y):.1f}" r="{r}"/>'


def _line(x1, y1, x2, y2, cls: str) -> str:
    return f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'


def _text(x, y, s: str, anchor: str = "start", cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{c}>{escape(s)}</text>'


def never_rechecked() -> float:
    return json.loads(NEVER.read_text())["test / uniform / 1 a week"]["never"][STALE]["value"]


def main() -> int:
    metrics = json.loads((RUN / "metrics.json").read_text())
    (RUN / "pareto.svg").write_text(svg(metrics, never_rechecked()))
    print(f"wrote {RUN / 'pareto.svg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
