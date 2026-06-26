#!/usr/bin/env python3
"""Render the ledger as a timeline SVG. Zero dependencies.

Each claim becomes a horizontal bar spanning valid_from -> valid_until, grouped
by topic, colored by status (active / superseded / contested). The point a
ledger makes visible: facts don't get deleted — they get a lifespan.

Usage:
  python3 tools/timeline_svg.py [--repo .] [--out assets/timeline.svg]
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger_core as core  # noqa: E402

BG = "#181133"
GRID = "#ffffff22"
TXT = "#EAE4FF"
DIM = "#9b8cd0"
ACTIVE = "#7C5CFC"
SUPER = "#5a5685"
CONTEST = "#ff6b6b"
NOW = "#3DDC97"
AMBER = "#FFB23E"

ROW_H = 30
PAD_L = 150
PAD_R = 40
TOPIC_GAP = 26


def _ord(d: str, fallback: int) -> int:
    if core._is_date(d):
        y, m, day = (int(x) for x in d.split("-"))
        return date(y, m, day).toordinal()
    return fallback


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(repo_root: str) -> str:
    claims, _ = core.load_claims(repo_root)
    today = date.today().toordinal()
    by_topic: dict = {}
    for c in claims:
        by_topic.setdefault(c.get("topic"), []).append(c)

    W = 820
    rows_total = sum(len(v) for v in by_topic.values())
    H = 92 + rows_total * ROW_H + len(by_topic) * TOPIC_GAP + 46

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">']
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>')
    out.append(f'<text x="24" y="34" fill="{TXT}" font-size="18" font-weight="600">'
               f'LLM Ledger — knowledge over time</text>')
    # legend (own row, below title)
    lg = [("active", ACTIVE), ("superseded", SUPER), ("contested", CONTEST)]
    lx = 24
    for label, col in lg:
        out.append(f'<rect x="{lx}" y="52" width="14" height="14" rx="3" fill="{col}"/>')
        out.append(f'<text x="{lx + 20}" y="64" fill="{DIM}" font-size="12">{label}</text>')
        lx += 110

    y = 88
    for topic, items in by_topic.items():
        canon = items[0].get("topic")
        out.append(f'<text x="24" y="{y + 14}" fill="{TXT}" font-size="14" '
                   f'font-weight="600">{_esc(canon)}</text>')
        # per-topic time range
        starts = [_ord(c.get("valid_from"), 10**9) for c in items]
        tmin = min([s for s in starts if s < 10**9] + [today])
        tmax = today
        span = max(tmax - tmin, 1)
        x0, x1 = PAD_L, W - PAD_R

        def mapx(o):
            return x0 + (o - tmin) / span * (x1 - x0)

        # year gridlines
        ys, ye = date.fromordinal(tmin).year, date.fromordinal(tmax).year
        step = max(1, (ye - ys) // 6)
        yr = ys
        while yr <= ye:
            gx = mapx(date(yr, 1, 1).toordinal())
            if x0 <= gx <= x1 - 30:
                out.append(f'<line x1="{gx:.0f}" y1="{y + 20}" x2="{gx:.0f}" '
                           f'y2="{y + 24 + len(items) * ROW_H}" stroke="{GRID}"/>')
                out.append(f'<text x="{gx:.0f}" y="{y + 16}" fill="{DIM}" '
                           f'font-size="10" text-anchor="middle">{yr}</text>')
            yr += step

        ry = y + 26
        for c in sorted(items, key=lambda c: _ord(c.get("valid_from"), 0)):
            status = c.get("status")
            col = {"active": ACTIVE, "superseded": SUPER,
                   "contested": CONTEST}.get(status, ACTIVE)
            unknown = not core._is_date(c.get("valid_from"))
            bs = _ord(c.get("valid_from"), tmin)
            be = _ord(c.get("valid_until"), today)
            bx, bw = mapx(bs), max(mapx(be) - mapx(bs), 6)
            out.append(f'<g><title>{_esc(c.get("id"))}: {_esc(c.get("statement"))}</title>')
            edge = f" stroke='{AMBER}' stroke-dasharray='3 2'" if unknown else ""
            op = 0.55 if status == "superseded" else 0.95
            out.append(f'<rect x="{bx:.0f}" y="{ry}" width="{bw:.0f}" height="20" rx="5" '
                       f'fill="{col}" opacity="{op}"{edge}/>')
            out.append(f'<text x="20" y="{ry + 14}" fill="{DIM}" font-size="11">'
                       f'{_esc(c.get("id"))}</text>')
            out.append('</g>')
            ry += ROW_H
        # now marker
        nx = mapx(today)
        out.append(f'<line x1="{nx:.0f}" y1="{y + 20}" x2="{nx:.0f}" y2="{ry}" '
                   f'stroke="{NOW}" stroke-width="1.5" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{nx - 4:.0f}" y="{y + 16}" fill="{NOW}" font-size="10" '
                   f'text-anchor="end">now</text>')
        y = ry + TOPIC_GAP

    out.append(f'<text x="24" y="{H - 12}" fill="{DIM}" font-size="11">'
               f'Faded = superseded (kept for as-of queries) · dashed edge = unknown start · '
               f'hover a bar for the claim</text>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--out", default="assets/timeline.svg")
    a = p.parse_args()
    svg = build_svg(a.repo)
    with open(os.path.join(a.repo, a.out), "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
