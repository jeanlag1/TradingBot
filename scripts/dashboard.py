"""Generate the strategy-zoo dashboard: a leaderboard of all paper models.

Reads every book under data/paper/, ranks them by risk-adjusted return, and
writes public/index.html — self-contained, theme-aware, inline SVG. The champion
(current live book) is highlighted; challengers are backfilled/compared beside
it. Judge on Sharpe + track record, never raw return (multiple-comparisons trap).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import metrics, models, paper

OUT = Path(__file__).resolve().parent.parent / "public" / "index.html"
VALIDATION_TARGET_DAYS = 60

# Palette slots (validated set, used in order) for the comparison lines.
LINE_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)",
               "var(--series-4)", "var(--series-5)"]


def _stats(book):
    curve = paper.equity_curve(book)
    if len(curve) < 2:
        return 0.0, 0.0
    rets = curve.pct_change().dropna()
    s = metrics.summary(rets, (rets != 0).astype(float))
    return s["sharpe"], metrics.max_drawdown(curve)


def multi_line(series_named):
    """series_named: list of (label, color, [equity multiples]) already indexed."""
    W, H = 900, 380
    L, R, T, B = 58, 74, 20, 30
    allv = [v for _, _, vs in series_named for v in vs]
    n = max(len(vs) for _, _, vs in series_named)
    vmin, vmax = min(allv), max(allv)
    pad = (vmax - vmin) * 0.08 or 0.01
    vmin, vmax = vmin - pad, vmax + pad

    def xy(i, v, ln):
        x = L + (i / (ln - 1 or 1)) * (W - R - L)
        y = (H - B) - (v - vmin) / ((vmax - vmin) or 1) * (H - B - T)
        return x, y

    grid = []
    for k in range(5):
        v = vmin + (vmax - vmin) * k / 4
        y = (H - B) - (v - vmin) / ((vmax - vmin) or 1) * (H - B - T)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" class="grid"/>'
                    f'<text x="{L-8}" y="{y+4:.1f}" class="tick" text-anchor="end">{v:.3f}x</text>')

    polys = []
    for label, color, vs in series_named:
        pts = [xy(i, v, len(vs)) for i, v in enumerate(vs)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        lx, ly = pts[-1]
        width = 2.4 if "series-1" in color else 1.8
        polys.append(f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="{width}"/>'
                     f'<text x="{lx+4:.1f}" y="{ly+4:.1f}" class="lbl" fill="{color}">{label}</text>')

    return f'''<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet">
  {''.join(grid)}{''.join(polys)}
</svg>'''


def leaderboard_table(rows):
    body = []
    for rank, r in enumerate(rows, 1):
        star = ' <span class="star">★ live</span>' if r["champion"] else ""
        rcls = ' class="champ"' if r["champion"] else ""
        ret_cls = "pos" if r["ret"] >= 0 else "neg"
        body.append(
            f'<tr{rcls}><td>{rank}</td><td><b>{r["name"]}</b>{star}<div class="why">{r["rationale"]}</div></td>'
            f'<td>{r["family"]}</td><td>{r["days"]}</td>'
            f'<td class="{ret_cls}">{r["ret"]:+.2%}</td><td>{r["sharpe"]:.2f}</td>'
            f'<td>{r["mdd"]:.1%}</td></tr>')
    return ('<table class="tbl"><thead><tr><th>#</th><th>Model</th><th>Family</th>'
            '<th>Days</th><th>Return</th><th>Sharpe</th><th>MaxDD</th></tr></thead><tbody>'
            + "".join(body) + "</tbody></table>")


def tile(label, value, cls=""):
    return f'<div class="tile"><div class="tile-l">{label}</div><div class="tile-v {cls}">{value}</div></div>'


def build():
    books = {b["name"]: b for b in paper.load_all()}
    rows = []
    for spec in models.ROSTER:
        b = books.get(spec.name)
        if not b:
            continue
        eq = b["history"][-1]["equity"] if b["history"] else b["start_equity"]
        sharpe, mdd = _stats(b)
        rows.append({"name": spec.name, "family": spec.family, "rationale": spec.rationale,
                     "days": len(b["history"]), "ret": eq / b["start_equity"] - 1,
                     "sharpe": sharpe, "mdd": mdd, "champion": spec.name == models.CHAMPION})
    rows.sort(key=lambda r: r["sharpe"], reverse=True)

    champ = next(r for r in rows if r["champion"])
    champ_rank = rows.index(champ) + 1
    best = rows[0]
    latest = books[models.CHAMPION]["history"][-1]["date"]
    n_days = champ["days"]

    tiles = "".join([
        tile("Models running", f"{len(rows)}"),
        tile("Top by Sharpe", best["name"]),
        tile("Champion rank", f"#{champ_rank} of {len(rows)}"),
        tile("Champion return", f"{champ['ret']:+.2%}", "good" if champ["ret"] >= 0 else "bad"),
        tile("Validation progress", f"{n_days} / {VALIDATION_TARGET_DAYS} days"),
    ])

    # Comparison chart: benchmark + champion + top-3 challengers, indexed to 1.00x.
    pick = ["hold_basket", models.CHAMPION]
    for r in rows:
        if r["name"] not in pick and len(pick) < 5:
            pick.append(r["name"])
    series = []
    for i, name in enumerate(pick):
        b = books[name]
        curve = paper.equity_curve(b)
        base = b["start_equity"]
        vals = [h["equity"] / base for h in b["history"]] or [1.0]
        series.append((name, LINE_COLORS[i % len(LINE_COLORS)], vals))

    html = (TEMPLATE
            .replace("__TILES__", tiles)
            .replace("__CHART__", multi_line(series))
            .replace("__TABLE__", leaderboard_table(rows))
            .replace("__LATEST__", latest)
            .replace("__NDAYS__", str(n_days)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"Wrote {OUT}  ({len(rows)} models)")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradingBot — Strategy Zoo</title>
<style>
:root{
  --plane:#f9f9f7; --surface-1:#fcfcfb; --text-primary:#0b0b0b; --text-secondary:#52514e;
  --muted:#898781; --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
  --series-1:#2a78d6; --series-2:#1baf7a; --series-3:#eda100; --series-4:#008300; --series-5:#4a3aa7;
  --good:#006300; --bad:#d03b3b; --champ-bg:rgba(42,120,214,.07);
}
@media (prefers-color-scheme:dark){:root{
  --plane:#0d0d0d; --surface-1:#1a1a19; --text-primary:#fff; --text-secondary:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
  --series-1:#3987e5; --series-2:#199e70; --series-3:#c98500; --series-4:#008300; --series-5:#9085e9;
  --good:#0ca30c; --bad:#e66767; --champ-bg:rgba(57,135,229,.12);
}}
*{box-sizing:border-box} body{margin:0;background:var(--plane);color:var(--text-primary);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 60px}
h1{font-size:22px;margin:0 0 2px} .sub{color:var(--text-secondary);font-size:14px;margin:0 0 24px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:26px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.tile-l{color:var(--text-secondary);font-size:12px;margin-bottom:6px}
.tile-v{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.tile-v.good{color:var(--good)} .tile-v.bad{color:var(--bad)}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:18px 18px 12px;margin-bottom:22px}
.card h2{font-size:15px;margin:0 0 2px} .card p{color:var(--text-secondary);font-size:13px;margin:0 0 10px}
.chart{width:100%;height:auto;display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.lbl{font-size:11px;font-weight:600}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{text-align:left;color:var(--text-secondary);font-weight:500;padding:8px;border-bottom:1px solid var(--border);
  font-variant-numeric:tabular-nums}
.tbl td{padding:9px 8px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums;vertical-align:top}
.tbl td:nth-child(3),.tbl td:nth-child(4){color:var(--text-secondary)}
.tbl tr.champ{background:var(--champ-bg)}
.tbl tr:last-child td{border-bottom:none}
.why{color:var(--muted);font-size:11.5px;font-weight:400;max-width:340px;margin-top:2px;line-height:1.35}
.star{color:var(--series-1);font-size:11px;font-weight:600;white-space:nowrap}
.pos{color:var(--good)} .neg{color:var(--bad)}
.note{background:var(--champ-bg);border:1px solid var(--border);border-radius:10px;padding:12px 14px;font-size:13px;
  color:var(--text-secondary);margin-bottom:22px}
.foot{color:var(--muted);font-size:12px;margin-top:24px}
</style></head><body><div class="wrap">
<h1>TradingBot — Strategy Zoo</h1>
<p class="sub">10 models on parallel <b>simulated</b> books (no real money) · BTC/ETH/SOL · latest __LATEST__ (__NDAYS__ days)</p>
<div class="tiles">__TILES__</div>
<div class="note"><b>How to read this:</b> ten strategies trade in parallel on paper so we get feedback fast without risk.
Ranked by <b>Sharpe</b> (risk-adjusted), not raw return — with ten candidates, one will look good by luck, so we judge on
risk-adjusted terms plus a minimum track record, and never crown a winner early. The ★ live model is the validated champion.</div>
<div class="card"><h2>Equity — benchmark vs champion vs top challengers</h2>
  <p>Growth of $1 since each book started, indexed to 1.00x. Shorter books (challengers) start where their data begins.</p>__CHART__</div>
<div class="card"><h2>Leaderboard</h2>
  <p>Every model, ranked by Sharpe. Return is raw P&amp;L; MaxDD is the realized peak-to-trough. Hover intent: the small text is each model's pre-registered rationale.</p>__TABLE__</div>
<p class="foot">Self-contained · updates daily via GitHub Actions → Vercel · paper trading only, no real money.</p>
</div></body></html>"""


if __name__ == "__main__":
    build()
