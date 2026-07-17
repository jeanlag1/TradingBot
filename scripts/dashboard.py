"""Generate a self-contained HTML dashboard from the paper book + backtest.

Reads data/paper_state.json (the live book) and re-runs the backtest for
context, then writes dashboard.html with inline-SVG charts (no external assets,
theme-aware). Regenerate after each daily --step. The charts use the validated
dataviz palette; categorical values are direct-labeled (light-mode relief rule).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import backtest, data, metrics, paper
from tradingbot.strategies import buy_and_hold, ensemble_momentum

OUT = Path(__file__).resolve().parent.parent / "dashboard.html"

# Validated palette slots (see references/palette.md).
SERIES = {"strat": "var(--series-1)", "hold": "var(--series-2)"}
ASSET_COLOR = {"BTC-USD": "var(--series-1)", "ETH-USD": "var(--series-2)",
               "SOL-USD": "var(--series-3)", "Cash": "var(--muted)"}


def _pts(values, x0, x1, y0, y1, vmin, vmax):
    n = len(values)
    span = (vmax - vmin) or 1.0
    out = []
    for i, v in enumerate(values):
        x = x0 + (i / (n - 1 or 1)) * (x1 - x0)
        y = y1 - (v - vmin) / span * (y1 - y0)
        out.append((x, y))
    return out


def line_chart(dates, strat, hold):
    W, H = 900, 360
    L, R, T, B = 58, 66, 20, 30
    vmin = min(min(strat), min(hold))
    vmax = max(max(strat), max(hold))
    pad = (vmax - vmin) * 0.08
    vmin, vmax = vmin - pad, vmax + pad
    sp = _pts(strat, L, W - R, T, H - B, vmin, vmax)
    hp = _pts(hold, L, W - R, T, H - B, vmin, vmax)

    grid, span = [], (vmax - vmin) or 1
    for k in range(5):
        v = vmin + span * k / 4
        y = (H - B) - (v - vmin) / span * (H - B - T)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" class="grid"/>'
                    f'<text x="{L-8}" y="{y+4:.1f}" class="tick" text-anchor="end">{v:.2f}x</text>')
    xticks = []
    for k in range(5):
        i = int(k * (len(dates) - 1) / 4)
        x = L + i / (len(dates) - 1) * (W - R - L)
        xticks.append(f'<text x="{x:.1f}" y="{H-10}" class="tick" text-anchor="middle">{dates[i][:7]}</text>')

    def poly(pts):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    sx, sy = sp[-1]
    hx, hy = hp[-1]
    return f'''<svg viewBox="0 0 {W} {H}" class="chart" id="equity" preserveAspectRatio="xMidYMid meet">
  {''.join(grid)}{''.join(xticks)}
  <polyline points="{poly(hp)}" fill="none" stroke="{SERIES['hold']}" stroke-width="2"/>
  <polyline points="{poly(sp)}" fill="none" stroke="{SERIES['strat']}" stroke-width="2"/>
  <text x="{sx-4:.1f}" y="{sy-6:.1f}" class="lbl" fill="{SERIES['strat']}" text-anchor="end">Strategy {strat[-1]:.2f}x</text>
  <text x="{hx-4:.1f}" y="{hy+14:.1f}" class="lbl" fill="{SERIES['hold']}" text-anchor="end">Buy &amp; Hold {hold[-1]:.2f}x</text>
  <g id="xhair" style="display:none"><line class="xhair-l"/><circle r="4" class="xhair-s"/><circle r="4" class="xhair-h"/></g>
  <rect x="{L}" y="{T}" width="{W-R-L}" height="{H-B-T}" fill="transparent" id="hit"/>
</svg>'''


def area_chart(dates, dd):
    W, H = 900, 170
    L, R, T, B = 58, 66, 14, 26
    vmin, vmax = min(dd), 0.0
    pts = _pts(dd, L, W - R, T, H - B, vmin, vmax)
    zero_y = (H - B) - (0 - vmin) / ((vmax - vmin) or 1) * (H - B - T)
    area = f"{L},{zero_y:.1f} " + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" {W-R},{zero_y:.1f}"
    ticks = []
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = vmin * frac
        y = zero_y - (v - 0) / ((vmin) or -1) * (zero_y - T) if vmin else zero_y
        y = (H - B) - (v - vmin) / ((vmax - vmin) or 1) * (H - B - T)
        ticks.append(f'<text x="{L-8}" y="{y+4:.1f}" class="tick" text-anchor="end">{v:.0%}</text>')
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f'''<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet">
  {''.join(ticks)}
  <polygon points="{area}" fill="var(--dd-fill)"/>
  <polyline points="{line}" fill="none" stroke="var(--dd-line)" stroke-width="2"/>
  <line x1="{L}" y1="{zero_y:.1f}" x2="{W-R}" y2="{zero_y:.1f}" class="baseline"/>
  <text x="{W-R}" y="{min(pts, key=lambda p: p[1])[1]+4:.0f}" class="lbl" fill="var(--dd-line)" text-anchor="end">min {min(dd):.0%}</text>
</svg>'''


def alloc_chart(weights):
    rows, y, bw = [], 12, 620
    for name, w in weights:
        wx = bw * min(w, 1.0)
        color = ASSET_COLOR.get(name, "var(--muted)")
        rows.append(
            f'<text x="0" y="{y+15}" class="alloc-name">{name.replace("-USD","")}</text>'
            f'<rect x="86" y="{y+3}" width="{max(wx,1):.1f}" height="16" rx="4" fill="{color}"/>'
            f'<text x="{86+max(wx,1)+8:.1f}" y="{y+15}" class="alloc-val">{w:.0%}</text>')
        y += 30
    return f'<svg viewBox="0 0 760 {y}" class="chart" preserveAspectRatio="xMidYMid meet">{"".join(rows)}</svg>'


def tile(label, value, cls=""):
    return f'<div class="tile"><div class="tile-l">{label}</div><div class="tile-v {cls}">{value}</div></div>'


def build():
    assets = ["BTC-USD", "ETH-USD", "SOL-USD"]
    dfs = {a: data.load(a) for a in assets}
    bt = backtest.run_portfolio(dfs, ensemble_momentum)
    hold = backtest.run_portfolio(dfs, buy_and_hold)
    stats = metrics.summary(bt.net_returns, bt.gross_exposure)

    dates = [str(d.date()) for d in bt.equity.index]
    strat = list(bt.equity.values)
    holdv = list(hold.equity.values)
    dd = list((bt.equity / bt.equity.cummax() - 1.0).values)

    st = paper.load_state()
    last = st["history"][-1]
    eq, start = last["equity"], st["start_equity"]
    ret = eq / start - 1
    cash_pct = last["cash"] / eq
    weights = [(a, last["weights"][a]) for a in assets] + [("Cash", cash_pct)]

    tiles = "".join([
        tile("Paper equity", f"${eq:,.0f}"),
        tile("Return since start", f"{ret:+.2%}", "good" if ret >= 0 else "bad"),
        tile("In cash (defensive)", f"{cash_pct:.0%}"),
        tile("Backtest Sharpe", f"{stats['sharpe']:.2f}"),
        tile("Backtest max drawdown", f"{stats['max_drawdown']:.0%}"),
    ])

    equity_json = json.dumps([{"t": dates[i], "s": round(strat[i], 4), "h": round(holdv[i], 4)}
                              for i in range(len(dates))])

    html = (TEMPLATE
            .replace("__TILES__", tiles)
            .replace("__EQUITY__", line_chart(dates, strat, holdv))
            .replace("__DD__", area_chart(dates, dd))
            .replace("__ALLOC__", alloc_chart(weights))
            .replace("__LATEST__", last["date"])
            .replace("__NSTEPS__", str(len(st["history"])))
            .replace("__EQJSON__", equity_json))
    OUT.write_text(html)
    print(f"Wrote {OUT}")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradingBot — Paper Dashboard</title>
<style>
:root{
  --plane:#f9f9f7; --surface-1:#fcfcfb; --text-primary:#0b0b0b; --text-secondary:#52514e;
  --muted:#898781; --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
  --series-1:#2a78d6; --series-2:#1baf7a; --series-3:#eda100;
  --good:#006300; --bad:#d03b3b; --dd-line:#d03b3b; --dd-fill:rgba(208,59,59,.14);
}
@media (prefers-color-scheme:dark){:root{
  --plane:#0d0d0d; --surface-1:#1a1a19; --text-primary:#fff; --text-secondary:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
  --series-1:#3987e5; --series-2:#199e70; --series-3:#c98500;
  --good:#0ca30c; --bad:#e66767; --dd-line:#e66767; --dd-fill:rgba(230,103,103,.16);
}}
*{box-sizing:border-box} body{margin:0;background:var(--plane);color:var(--text-primary);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 60px}
h1{font-size:22px;margin:0 0 2px} .sub{color:var(--text-secondary);font-size:14px;margin:0 0 24px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:26px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.tile-l{color:var(--text-secondary);font-size:12px;margin-bottom:6px}
.tile-v{font-size:26px;font-weight:600} .tile-v.good{color:var(--good)} .tile-v.bad{color:var(--bad)}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:18px 18px 8px;margin-bottom:22px}
.card h2{font-size:15px;margin:0 0 2px} .card p{color:var(--text-secondary);font-size:13px;margin:0 0 10px}
.chart{width:100%;height:auto;display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1} .baseline{stroke:var(--baseline);stroke-width:1}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.lbl{font-size:12px;font-weight:600} .alloc-name{fill:var(--text-secondary);font-size:13px}
.alloc-val{fill:var(--text-primary);font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
.xhair-l{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3}
.xhair-s{fill:var(--series-1)} .xhair-h{fill:var(--series-2)}
#tip{position:fixed;pointer-events:none;background:var(--surface-1);border:1px solid var(--border);
  border-radius:8px;padding:8px 10px;font-size:12px;display:none;box-shadow:0 4px 14px rgba(0,0,0,.14);z-index:9}
#tip b{font-variant-numeric:tabular-nums} .dot-s{color:var(--series-1)} .dot-h{color:var(--series-2)}
.foot{color:var(--muted);font-size:12px;margin-top:24px}
</style></head><body><div class="wrap">
<h1>TradingBot — Paper Trading Dashboard</h1>
<p class="sub">Ensemble-momentum basket · BTC / ETH / SOL · spot long-flat · latest step __LATEST__ (__NSTEPS__ steps)</p>
<div class="tiles">__TILES__</div>
<div class="card"><h2>Equity curve — strategy vs. buy &amp; hold</h2>
  <p>Backtested growth of $1. The strategy trades most of the upside for far shallower drawdowns.</p>__EQUITY__</div>
<div class="card"><h2>Strategy drawdown</h2><p>Peak-to-trough decline. Momentum's job is to keep this shallow by moving to cash.</p>__DD__</div>
<div class="card"><h2>Current allocation (live paper book)</h2>
  <p>Target weights the bot holds right now. Cash is the defensive residual when trends are weak.</p>__ALLOC__</div>
<p class="foot">Self-contained · regenerate with <code>python scripts/dashboard.py</code> after each daily step.</p>
</div>
<div id="tip"></div>
<script>
const DATA=__EQJSON__;
const svg=document.getElementById('equity'),hit=document.getElementById('hit'),
  xh=document.getElementById('xhair'),tip=document.getElementById('tip');
const L=58,R=66,T=20,B=30,W=900,H=360;
let vmin=Infinity,vmax=-Infinity;for(const d of DATA){vmin=Math.min(vmin,d.s,d.h);vmax=Math.max(vmax,d.s,d.h);}
const pd=(vmax-vmin)*0.08;vmin-=pd;vmax+=pd;
const X=i=>L+i/(DATA.length-1)*(W-R-L), Y=v=>(H-B)-(v-vmin)/(vmax-vmin)*(H-B-T);
hit.addEventListener('mousemove',e=>{
  const r=svg.getBoundingClientRect(),px=(e.clientX-r.left)/r.width*W;
  let i=Math.round((px-L)/(W-R-L)*(DATA.length-1));i=Math.max(0,Math.min(DATA.length-1,i));
  const d=DATA[i];xh.style.display='';
  const ln=xh.querySelector('line');ln.setAttribute('x1',X(i));ln.setAttribute('x2',X(i));
  ln.setAttribute('y1',T);ln.setAttribute('y2',H-B);
  const cs=xh.querySelectorAll('circle');cs[0].setAttribute('cx',X(i));cs[0].setAttribute('cy',Y(d.s));
  cs[1].setAttribute('cx',X(i));cs[1].setAttribute('cy',Y(d.h));
  tip.style.display='block';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';
  tip.innerHTML=`<div>${d.t}</div><div class="dot-s">● Strategy <b>${d.s.toFixed(2)}x</b></div><div class="dot-h">● Buy&amp;Hold <b>${d.h.toFixed(2)}x</b></div>`;
});
hit.addEventListener('mouseleave',()=>{xh.style.display='none';tip.style.display='none';});
</script></body></html>"""


if __name__ == "__main__":
    build()
