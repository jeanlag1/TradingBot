"""Generate the multi-page strategy-zoo dashboard.

  public/index.html          home: leaderboard + comparison, links to each model
  public/models/<name>.html  per-model analysis: stats, equity, daily decisions

Self-contained, theme-aware, inline SVG. Judge on Sharpe + track record, never
raw return (the multiple-comparisons trap). Detail per day includes the actual
buy/sell/hold and the plain-English reason the model did or didn't trade.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import graduation, metrics, models, paper

PUB = Path(__file__).resolve().parent.parent / "public"
VALIDATION_TARGET_DAYS = 60
LINE_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)",
               "var(--series-4)", "var(--series-5)"]
ACTIVITY_DAYS = 30

STYLE = """<style>
:root{
  --plane:#f9f9f7; --surface-1:#fcfcfb; --text-primary:#0b0b0b; --text-secondary:#52514e;
  --muted:#898781; --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
  --series-1:#2a78d6; --series-2:#1baf7a; --series-3:#eda100; --series-4:#008300; --series-5:#4a3aa7;
  --good:#006300; --bad:#d03b3b; --champ-bg:rgba(42,120,214,.07);
  --buy:#006300; --sell:#d03b3b; --hold:#898781;
}
@media (prefers-color-scheme:dark){:root{
  --plane:#0d0d0d; --surface-1:#1a1a19; --text-primary:#fff; --text-secondary:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
  --series-1:#3987e5; --series-2:#199e70; --series-3:#c98500; --series-4:#008300; --series-5:#9085e9;
  --good:#0ca30c; --bad:#e66767; --champ-bg:rgba(57,135,229,.12);
  --buy:#0ca30c; --sell:#e66767; --hold:#898781;
}}
*{box-sizing:border-box} body{margin:0;background:var(--plane);color:var(--text-primary);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 60px}
a{color:var(--series-1);text-decoration:none} a:hover{text-decoration:underline}
h1{font-size:22px;margin:0 0 2px} .sub{color:var(--text-secondary);font-size:14px;margin:0 0 24px}
.back{font-size:13px;display:inline-block;margin-bottom:14px}
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
.tbl th{text-align:left;color:var(--text-secondary);font-weight:500;padding:8px;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums}
.tbl td{padding:9px 8px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums;vertical-align:top}
.tbl tr.champ{background:var(--champ-bg)} .tbl tr:last-child td{border-bottom:none}
.why{color:var(--muted);font-size:11.5px;font-weight:400;max-width:340px;margin-top:2px;line-height:1.35}
.star{color:var(--series-1);font-size:11px;font-weight:600;white-space:nowrap}
.pos{color:var(--good)} .neg{color:var(--bad)}
.act{font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.02em}
.act.buy{color:var(--buy)} .act.short{color:var(--sell)} .act.sell{color:var(--sell)} .act.hold{color:var(--hold)}
.daterow td{border-top:2px solid var(--border);font-weight:600}
.gate{display:flex;align-items:baseline;gap:8px;padding:7px 0;border-bottom:1px solid var(--grid);font-size:13px}
.gate:last-child{border-bottom:none} .gate .mark{font-weight:700;width:16px}
.gate.pass .mark{color:var(--good)} .gate.fail .mark{color:var(--muted)}
.gate .g-detail{color:var(--muted);font-size:12px;margin-left:auto;font-variant-numeric:tabular-nums}
.gate.manual .mark{color:var(--series-3)}
.note{background:var(--champ-bg);border:1px solid var(--border);border-radius:10px;padding:12px 14px;font-size:13px;
  color:var(--text-secondary);margin-bottom:22px}
.foot{color:var(--muted);font-size:12px;margin-top:24px}
</style>"""


def page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{title}</title>{STYLE}</head><body><div class="wrap">{body}</div></body></html>')


def tile(label, value, cls=""):
    return f'<div class="tile"><div class="tile-l">{label}</div><div class="tile-v {cls}">{value}</div></div>'


def multi_line(series_named):
    W, H = 900, 360
    L, R, T, B = 58, 90, 20, 30
    allv = [v for _, _, vs in series_named for v in vs]
    vmin, vmax = min(allv), max(allv)
    pad = (vmax - vmin) * 0.08 or 0.01
    vmin, vmax = vmin - pad, vmax + pad

    def xy(i, v, ln):
        return (L + (i / (ln - 1 or 1)) * (W - R - L),
                (H - B) - (v - vmin) / ((vmax - vmin) or 1) * (H - B - T))

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
                     f'<text x="{lx+5:.1f}" y="{ly+4:.1f}" class="lbl" fill="{color}">{label}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet">'
            f'{"".join(grid)}{"".join(polys)}</svg>')


# ------------------------------------------------------------------- home ---
def leaderboard_table(rows):
    body = []
    for rank, r in enumerate(rows, 1):
        star = ' <span class="star">★ live</span>' if r["champion"] else ""
        rcls = ' class="champ"' if r["champion"] else ""
        ret_cls = "pos" if r["ret"] >= 0 else "neg"
        body.append(
            f'<tr{rcls}><td>{rank}</td>'
            f'<td><a href="/models/{r["name"]}"><b>{r["name"]}</b></a>{star}'
            f'<div class="why">{r["rationale"]}</div></td>'
            f'<td>{r["family"]}</td><td>{r["days"]}</td>'
            f'<td class="{ret_cls}">{r["ret"]:+.2%}</td><td>{r["sharpe"]:.2f}</td>'
            f'<td>{r["mdd"]:.1%}</td></tr>')
    return ('<table class="tbl"><thead><tr><th>#</th><th>Model</th><th>Family</th>'
            '<th>Days</th><th>Return</th><th>Sharpe</th><th>MaxDD</th></tr></thead><tbody>'
            + "".join(body) + "</tbody></table>")


def build_home(rows, books, latest):
    champ = next(r for r in rows if r["champion"])
    champ_rank = rows.index(champ) + 1
    best = rows[0]
    n_days = champ["days"]
    tiles = "".join([
        tile("Models running", f"{len(rows)}"),
        tile("Top by Sharpe", f'<a href="/models/{best["name"]}">{best["name"]}</a>'),
        tile("Champion rank", f"#{champ_rank} of {len(rows)}"),
        tile("Champion return", f"{champ['ret']:+.2%}", "good" if champ["ret"] >= 0 else "bad"),
        tile("Validation", f"{n_days} / {VALIDATION_TARGET_DAYS} days"),
    ])
    pick = ["hold_basket", models.CHAMPION]
    for r in rows:
        if r["name"] not in pick and len(pick) < 5:
            pick.append(r["name"])
    series = []
    for i, name in enumerate(pick):
        b = books[name]
        vals = [h["equity"] / b["start_equity"] for h in b["history"]] or [1.0]
        series.append((name, LINE_COLORS[i % len(LINE_COLORS)], vals))

    body = (
        '<h1>TradingBot — Strategy Zoo</h1>'
        f'<p class="sub">10 models on parallel <b>simulated</b> books (no real money) · '
        f'BTC/ETH/SOL · latest {latest} ({n_days} days)</p>'
        f'<div class="tiles">{tiles}</div>'
        '<div class="note"><b>How to read this:</b> ten strategies trade in parallel on paper for fast feedback '
        'without risk. Ranked by <b>Sharpe</b> (risk-adjusted), not raw return — with ten candidates one will look '
        'good by luck, so we judge on risk-adjusted terms plus a track record, and never crown a winner early. '
        'Click any model for its daily decisions. The ★ live model is the validated champion.</div>'
        '<div class="card"><h2>Equity — benchmark vs champion vs top challengers</h2>'
        '<p>Growth of $1 since each book started, indexed to 1.00x.</p>' + multi_line(series) + '</div>'
        '<div class="card"><h2>Leaderboard</h2>'
        '<p>Every model, ranked by Sharpe. The small text is each model\'s pre-registered rationale. '
        'Click a name for its full daily activity.</p>' + leaderboard_table(rows) + '</div>'
        '<p class="foot">Self-contained · updates daily via GitHub Actions → Vercel · paper trading only.</p>')
    (PUB / "index.html").write_text(page("TradingBot — Strategy Zoo", body))


# ------------------------------------------------------------- model page ---
def activity_table(history):
    out = ['<table class="tbl"><thead><tr><th>Date</th><th>Asset</th><th>Signal</th>'
           '<th>Action</th><th>$ Traded</th><th>Held</th><th>Why</th></tr></thead><tbody>']
    for h in reversed(history[-ACTIVITY_DAYS:]):
        legs = h.get("legs", [])
        for j, l in enumerate(legs):
            datecell = (f'{h["date"]}<div class="why">equity ${h["equity"]:,.0f}</div>') if j == 0 else ""
            rowcls = ' class="daterow"' if j == 0 else ""
            traded = f'${l["traded_usd"]:+,.0f}' if abs(l["traded_usd"]) >= 1 else "—"
            held = f'${l["held_usd"]:,.0f}' if abs(l["held_usd"]) >= 1 else "—"
            out.append(
                f'<tr{rowcls}><td>{datecell}</td><td>{l["asset"].replace("-USD","")}</td>'
                f'<td>{l["signal"]:+.0%}</td>'
                f'<td><span class="act {l["action"]}">{l["action"]}</span></td>'
                f'<td>{traded}</td><td>{held}</td>'
                f'<td class="why">{l["reason"]}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def graduation_card(spec, book, champ_stats):
    sharpe, mdd = _stats(book)
    stats = {"days": len(book["history"]), "sharpe": sharpe, "mdd": mdd}
    result = graduation.evaluate(stats, champ_stats, spec.name == models.CHAMPION)
    rows = []
    for label, passed, detail in result["gates"]:
        cls = "pass" if passed else "fail"
        mark = "✓" if passed else "○"
        rows.append(f'<div class="gate {cls}"><span class="mark">{mark}</span>'
                    f'<span>{label}</span><span class="g-detail">{detail}</span></div>')
    for label in result["manual"]:
        rows.append(f'<div class="gate manual"><span class="mark">◐</span>'
                    f'<span>{label}</span><span class="g-detail">manual review</span></div>')
    if result["is_champion"]:
        verdict = "Incumbent champion — the bar every challenger must clear."
    elif result["eligible_pending_review"]:
        verdict = "Auto-gates cleared — pending manual regime + walk-forward review."
    else:
        verdict = "Not yet eligible. Gates 1–3 are automatic; 4–5 are manual once 1–3 pass."
    return ('<div class="card"><h2>Graduation progress</h2>'
            f'<p>The pre-registered bar to be considered for real money '
            f'(<a href="https://github.com/jeanlag1/TradingBot/blob/main/docs/graduation.md">docs/graduation.md</a>). '
            f'{verdict}</p>' + "".join(rows) + '</div>')


def build_model_page(spec, book, hold_book, champ_stats):
    curve = paper.equity_curve(book)
    eq = book["history"][-1]["equity"]
    ret = eq / book["start_equity"] - 1
    sharpe, mdd = _stats(book)
    total_trades = sum(h["trades"] for h in book["history"])
    days_traded = sum(1 for h in book["history"] if h["trades"] > 0)

    tiles = "".join([
        tile("Return", f"{ret:+.2%}", "good" if ret >= 0 else "bad"),
        tile("Sharpe", f"{sharpe:.2f}"),
        tile("Max drawdown", f"{mdd:.1%}"),
        tile("Days traded", f"{days_traded} / {len(book['history'])}"),
        tile("Total rebalances", f"{total_trades}"),
    ])
    series = [(spec.name, "var(--series-1)",
               [h["equity"] / book["start_equity"] for h in book["history"]] or [1.0])]
    if hold_book and spec.name != "hold_basket":
        series.append(("hold_basket", "var(--series-2)",
                       [h["equity"] / hold_book["start_equity"] for h in hold_book["history"]] or [1.0]))

    body = (
        '<a class="back" href="/">← all models</a>'
        f'<h1>{spec.name} <span class="star">{"★ live champion" if spec.name==models.CHAMPION else spec.family}</span></h1>'
        f'<p class="sub">{spec.rationale}</p>'
        f'<div class="tiles">{tiles}</div>'
        '<div class="card"><h2>Equity vs benchmark</h2>'
        '<p>Growth of $1 since start, indexed to 1.00x (aqua = buy&amp;hold benchmark).</p>'
        + multi_line(series) + '</div>'
        + graduation_card(spec, book, champ_stats) +
        '<div class="card"><h2>Daily decisions — last '
        f'{min(ACTIVITY_DAYS, len(book["history"]))} days</h2>'
        '<p>What the model did each day and why. Signal is its conviction per asset '
        '(0% = flat, 100% = full long, negative = short); a trade only fires when the target '
        'moves past the rebalance band.</p>' + activity_table(book["history"]) + '</div>'
        '<a class="back" href="/">← all models</a>')
    (PUB / "models" / f"{spec.name}.html").write_text(page(f"{spec.name} — TradingBot", body))


def _stats(book):
    curve = paper.equity_curve(book)
    if len(curve) < 2:
        return 0.0, 0.0
    rets = curve.pct_change().dropna()
    s = metrics.summary(rets, (rets != 0).astype(float))
    return s["sharpe"], metrics.max_drawdown(curve)


def build():
    (PUB / "models").mkdir(parents=True, exist_ok=True)
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
    latest = books[models.CHAMPION]["history"][-1]["date"]

    build_home(rows, books, latest)
    hold = books.get("hold_basket")
    champ = books[models.CHAMPION]
    cs, cm = _stats(champ)
    champ_stats = {"days": len(champ["history"]), "sharpe": cs, "mdd": cm}
    for spec in models.ROSTER:
        if spec.name in books:
            build_model_page(spec, books[spec.name], hold, champ_stats)
    print(f"Wrote {PUB/'index.html'} + {len(rows)} model pages")


if __name__ == "__main__":
    build()
