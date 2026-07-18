"""Generate a self-contained HTML dashboard from the paper book + backtest.

Reads data/paper_state.json (the live book) and re-runs the backtest for
context, then writes public/index.html with inline-SVG charts (no external
assets, theme-aware). Regenerate after each daily --step. Charts use the
validated dataviz palette; categorical values are direct-labeled (light-mode
relief rule).

Sections:
  * stat tiles (incl. validation progress toward the multi-week gate)
  * live vs. backtest overlay — the headline: realized paper equity against what
    the backtest expected over the same window (degrades gracefully while sparse)
  * current positioning — allocation + per-asset signal strength
  * backtest context — equity curve (hover crosshair) and drawdown
  * recent activity log
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import backtest, data, metrics, paper
from tradingbot.strategies import buy_and_hold, ensemble_momentum

OUT = Path(__file__).resolve().parent.parent / "public" / "index.html"
VALIDATION_TARGET_DAYS = 21  # ~3 weeks of steps before we trust the live track

SERIES = {"strat": "var(--series-1)", "hold": "var(--series-2)"}
ASSET_COLOR = {"BTC-USD": "var(--series-1)", "ETH-USD": "var(--series-2)",
               "SOL-USD": "var(--series-3)", "Cash": "var(--muted)"}


def _pts(values, x0, x1, y0, y1, vmin, vmax):
    n = len(values)
    span = (vmax - vmin) or 1.0
    return [(x0 + (i / (n - 1 or 1)) * (x1 - x0),
             y1 - (v - vmin) / span * (y1 - y0)) for i, v in enumerate(values)]


def line_chart(dates, strat, hold):
    W, H = 900, 360
    L, R, T, B = 58, 66, 20, 30
    vmin, vmax = min(min(strat), min(hold)), max(max(strat), max(hold))
    pad = (vmax - vmin) * 0.08
    vmin, vmax = vmin - pad, vmax + pad
    sp, hp = _pts(strat, L, W - R, T, H - B, vmin, vmax), _pts(hold, L, W - R, T, H - B, vmin, vmax)

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


def validation_chart(pdates, realized, expected):
    """Realized paper equity vs. backtest-expected, both indexed to 1.0 at the
    paper start. A widening gap = live is diverging from the backtest."""
    W, H = 900, 300
    L, R, T, B = 58, 66, 22, 34
    allv = realized + expected
    lo, hi = min(allv), max(allv)
    c, half = (lo + hi) / 2, max((hi - lo) / 2, 0.012)  # floor the band at ±1.2%
    vmin, vmax = c - half * 1.3, c + half * 1.3
    n = len(pdates)

    def pts(vals):
        return [(L + (i / (n - 1 or 1)) * (W - R - L),
                 (H - B) - (v - vmin) / ((vmax - vmin) or 1) * (H - B - T)) for i, v in enumerate(vals)]

    ep, rp = pts(expected), pts(realized)
    grid = []
    for k in range(3):
        v = vmin + (vmax - vmin) * k / 2
        y = (H - B) - (v - vmin) / ((vmax - vmin) or 1) * (H - B - T)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" class="grid"/>'
                    f'<text x="{L-8}" y="{y+4:.1f}" class="tick" text-anchor="end">{v:.3f}x</text>')
    xt = (f'<text x="{L}" y="{H-10}" class="tick" text-anchor="start">{pdates[0]}</text>'
          f'<text x="{W-R}" y="{H-10}" class="tick" text-anchor="end">{pdates[-1]}</text>')

    def poly(p):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in p)

    def dots(p, cls):
        return "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" class="{cls}"/>' for x, y in p)

    gap = realized[-1] - expected[-1]
    note = "" if n > 1 else (f'<text x="{(L+W-R)/2:.0f}" y="{H/2:.0f}" class="note" '
                             f'text-anchor="middle">Accumulating — {n} step. The lines fill in each day.</text>')
    return f'''<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet">
  {''.join(grid)}{xt}
  <polyline points="{poly(ep)}" fill="none" stroke="var(--muted)" stroke-width="2" stroke-dasharray="5 4"/>
  <polyline points="{poly(rp)}" fill="none" stroke="{SERIES['strat']}" stroke-width="2"/>
  {dots(ep,'d-exp')}{dots(rp,'d-real')}
  <text x="{rp[-1][0]-4:.1f}" y="{rp[-1][1]-8:.1f}" class="lbl" fill="{SERIES['strat']}" text-anchor="end">Realized (paper)</text>
  <text x="{ep[-1][0]-4:.1f}" y="{ep[-1][1]+16:.1f}" class="lbl" fill="var(--muted)" text-anchor="end">Backtest-expected</text>
  {note}
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
    rows, y, bw = [], 12, 560
    for name, w in weights:
        wx = bw * min(w, 1.0)
        color = ASSET_COLOR.get(name, "var(--muted)")
        rows.append(
            f'<text x="0" y="{y+15}" class="alloc-name">{name.replace("-USD","")}</text>'
            f'<rect x="86" y="{y+3}" width="{max(wx,1):.1f}" height="16" rx="4" fill="{color}"/>'
            f'<text x="{86+max(wx,1)+8:.1f}" y="{y+15}" class="alloc-val">{w:.0%}</text>')
        y += 30
    return f'<svg viewBox="0 0 700 {y}" class="chart" preserveAspectRatio="xMidYMid meet">{"".join(rows)}</svg>'


def per_asset_table(rows):
    body = []
    for name, sig, pos_val, tr in rows:
        color = ASSET_COLOR.get(name, "var(--muted)")
        trend_cls = "pos" if tr >= 0 else "neg"
        body.append(
            f'<tr><td><b>{name.replace("-USD","")}</b></td>'
            f'<td><span class="mini"><i style="width:{sig*100:.0f}%;background:{color}"></i></span>'
            f' {sig:.0%}</td>'
            f'<td>${pos_val:,.0f}</td>'
            f'<td class="{trend_cls}">{tr:+.1%}</td></tr>')
    return ('<table class="tbl"><thead><tr><th>Asset</th><th>Signal (ensemble)</th>'
            '<th>Held</th><th>90d trend</th></tr></thead><tbody>'
            + "".join(body) + "</tbody></table>")


def activity_table(history):
    body = []
    for h in reversed(history[-15:]):
        cash_pct = h["cash"] / h["equity"] if h["equity"] else 0
        body.append(
            f'<tr><td>{h["date"]}</td><td>${h["equity"]:,.2f}</td>'
            f'<td>{h["trades"]}</td><td>{cash_pct:.0%}</td></tr>')
    return ('<table class="tbl"><thead><tr><th>Date</th><th>Equity</th>'
            '<th>Rebalances</th><th>Cash</th></tr></thead><tbody>'
            + "".join(body) + "</tbody></table>")


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
    hist = st["history"]
    last = hist[-1]
    eq, start = last["equity"], st["start_equity"]
    ret = eq / start - 1
    cash_pct = last["cash"] / eq
    weights = [(a, last["weights"][a]) for a in assets] + [("Cash", cash_pct)]

    # Per-asset signal + position + trailing trend.
    per_rows = []
    for a in assets:
        sig = float(ensemble_momentum(dfs[a]).iloc[-1])
        pos_val = st["units"][a] * last["prices"][a]
        tr90 = float(dfs[a]["close"].pct_change(90).iloc[-1])
        per_rows.append((a, sig, pos_val, tr90))

    # Live vs. backtest overlay, both indexed to 1.0 at the paper start date.
    bt_by_date = {str(d.date()): float(v) for d, v in bt.equity.items()}
    pdates = [h["date"] for h in hist]
    peq = [h["equity"] for h in hist]
    base_p = peq[0] or 1.0
    base_b = bt_by_date.get(pdates[0], strat[-1]) or 1.0
    realized = [e / base_p for e in peq]
    expected = [bt_by_date.get(d, base_b) / base_b for d in pdates]
    gap = realized[-1] - expected[-1]

    n_days = len(hist)
    tiles = "".join([
        tile("Paper equity", f"${eq:,.0f}"),
        tile("Return since start", f"{ret:+.2%}", "good" if ret >= 0 else "bad"),
        tile("Validation progress", f"{n_days} / {VALIDATION_TARGET_DAYS} days"),
        tile("Live vs. backtest gap", f"{gap:+.2%}", "good" if abs(gap) < 0.01 else "bad"),
        tile("In cash (defensive)", f"{cash_pct:.0%}"),
    ])

    equity_json = json.dumps([{"t": dates[i], "s": round(strat[i], 4), "h": round(holdv[i], 4)}
                              for i in range(len(dates))])

    html = (TEMPLATE
            .replace("__TILES__", tiles)
            .replace("__VALIDATION__", validation_chart(pdates, realized, expected))
            .replace("__ALLOC__", alloc_chart(weights))
            .replace("__PERASSET__", per_asset_table(per_rows))
            .replace("__EQUITY__", line_chart(dates, strat, holdv))
            .replace("__DD__", area_chart(dates, dd))
            .replace("__ACTIVITY__", activity_table(hist))
            .replace("__LATEST__", last["date"])
            .replace("__NSTEPS__", str(n_days))
            .replace("__EQJSON__", equity_json))
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:26px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.tile-l{color:var(--text-secondary);font-size:12px;margin-bottom:6px}
.tile-v{font-size:24px;font-weight:600;font-variant-numeric:tabular-nums}
.tile-v.good{color:var(--good)} .tile-v.bad{color:var(--bad)}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:12px;padding:18px 18px 12px;margin-bottom:22px}
.card h2{font-size:15px;margin:0 0 2px} .card p{color:var(--text-secondary);font-size:13px;margin:0 0 10px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:22px}
@media (max-width:680px){.cols{grid-template-columns:1fr}}
.chart{width:100%;height:auto;display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1} .baseline{stroke:var(--baseline);stroke-width:1}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.note{fill:var(--muted);font-size:13px}
.lbl{font-size:12px;font-weight:600} .alloc-name{fill:var(--text-secondary);font-size:13px}
.alloc-val{fill:var(--text-primary);font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
.d-real{fill:var(--series-1)} .d-exp{fill:var(--muted)}
.xhair-l{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3}
.xhair-s{fill:var(--series-1)} .xhair-h{fill:var(--series-2)}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{text-align:left;color:var(--text-secondary);font-weight:500;padding:6px 8px;border-bottom:1px solid var(--border)}
.tbl td{padding:7px 8px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums}
.tbl tr:last-child td{border-bottom:none}
.mini{background:var(--grid);border-radius:4px;height:8px;width:90px;display:inline-block;vertical-align:middle}
.mini i{display:block;height:8px;border-radius:4px}
.pos{color:var(--good)} .neg{color:var(--bad)}
#tip{position:fixed;pointer-events:none;background:var(--surface-1);border:1px solid var(--border);
  border-radius:8px;padding:8px 10px;font-size:12px;display:none;box-shadow:0 4px 14px rgba(0,0,0,.14);z-index:9}
#tip b{font-variant-numeric:tabular-nums} .dot-s{color:var(--series-1)} .dot-h{color:var(--series-2)}
.foot{color:var(--muted);font-size:12px;margin-top:24px}
</style></head><body><div class="wrap">
<h1>TradingBot — Paper Trading Dashboard</h1>
<p class="sub">Ensemble-momentum basket · BTC / ETH / SOL · spot long-flat · <b>simulated</b> (no real money) · latest step __LATEST__ (__NSTEPS__ steps)</p>
<div class="tiles">__TILES__</div>
<div class="card"><h2>Live vs. backtest — validation window</h2>
  <p>Realized paper equity against what the backtest expected over the same days, both from 1.00x at the start. They should track closely; a widening gap means live is diverging from the backtest.</p>__VALIDATION__</div>
<div class="cols">
  <div class="card"><h2>Current allocation</h2>
    <p>Weights held right now. Cash is the defensive residual.</p>__ALLOC__</div>
  <div class="card"><h2>Per-asset signal &amp; position</h2>
    <p>Ensemble signal strength (0–100%) and what's held, per asset.</p>__PERASSET__</div>
</div>
<div class="card"><h2>Equity curve — strategy vs. buy &amp; hold (backtest)</h2>
  <p>Backtested growth of $1. The strategy trades most of the upside for far shallower drawdowns.</p>__EQUITY__</div>
<div class="card"><h2>Strategy drawdown (backtest)</h2><p>Peak-to-trough decline. Momentum keeps this shallow by moving to cash.</p>__DD__</div>
<div class="card"><h2>Recent activity</h2><p>The last steps the bot took — equity, rebalances, and cash level each day.</p>__ACTIVITY__</div>
<p class="foot">Self-contained · updates daily via GitHub Actions → Vercel · paper trading only.</p>
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
