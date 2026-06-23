from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

from .metrics import Trade


def write_html_report(
    path: Path,
    summary: dict[str, object],
    trades: list[Trade],
) -> None:
    equity = _equity_points(trades)
    drawdown = _drawdown_points(equity)
    monthly = _monthly_points(trades)
    best = summary["best"]
    top = summary["top"]

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TimeProfitEA Optimization Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17191c;
      --muted: #646b76;
      --line: #d9dee7;
      --good: #137b47;
      --bad: #b42318;
      --blue: #1f6feb;
      --amber: #9a6700;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", Arial, sans-serif;
      line-height: 1.45;
    }}
    header {{
      background: #1d232f;
      color: #fff;
      padding: 24px 28px;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 24px; }}
    h2 {{ font-size: 18px; margin-bottom: 14px; }}
    h3 {{ font-size: 15px; margin-bottom: 10px; }}
    .subtle {{ color: #d4d9e2; margin-top: 6px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 18px;
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .metric .value {{
      font-size: 24px;
      font-weight: 650;
      white-space: nowrap;
    }}
    .positive {{ color: var(--good); }}
    .negative {{ color: var(--bad); }}
    .chart {{
      width: 100%;
      height: 280px;
      display: block;
    }}
    .charts {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 7px;
      text-align: right;
      white-space: nowrap;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #fafbfc;
    }}
    .scroll {{ overflow-x: auto; }}
    .params {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }}
    .param {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfe;
    }}
    .param span {{ display: block; color: var(--muted); font-size: 12px; }}
    .param strong {{ display: block; font-size: 20px; margin-top: 2px; }}
    @media (max-width: 860px) {{
      main {{ padding: 14px; }}
      .grid, .charts, .params {{ grid-template-columns: 1fr; }}
      header {{ padding: 20px 16px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>TimeProfitEA 参数优化报告</h1>
    <div class="subtle">数据窗口：{escape(str(summary["from"]))} 至 {escape(str(summary["to"]))}，Bars：{summary["bars_used"]}</div>
    {_excluded_dates_note(summary)}
  </header>
  <main>
    <section class="grid">
      {_metric("净收益点数", _fmt(best["net_points"]), best["net_points"])}
      {_metric("最大回撤点数", _fmt(best["max_drawdown_points"]), -float(best["max_drawdown_points"]))}
      {_metric("Profit Factor", _fmt(best["profit_factor"]), best["profit_factor"])}
      {_metric("交易次数", str(best["trade_count"]), best["trade_count"])}
    </section>

    <section class="panel">
      <h2>最佳参数</h2>
      <div class="params">
        {_param("EMA 快线", best["ema_fast"])}
        {_param("EMA 慢线", best["ema_slow"])}
        {_param("时间止盈分钟", best["time_check_minutes"])}
        {_param("止损点数", best["stop_loss_points"])}
        {_param("冷却分钟", best["cooldown_minutes"])}
        {_param("保本止损", best.get("use_break_even_stop", True))}
        {_param("保本启动点数", best.get("break_even_start_points", 500))}
        {_param("保本锁盈点数", best.get("break_even_lock_points", 30))}
        {_param("回撤平仓", best.get("use_profit_giveback_close", True))}
        {_param("回撤启动点数", best.get("giveback_start_points", 1500))}
        {_param("回撤平仓点数", best.get("giveback_close_points", 700))}
        {_param("回撤平仓比例", best.get("giveback_close_percent", 80.0))}
      </div>
    </section>

    <section class="charts">
      <div class="panel">
        <h2>最佳参数权益曲线</h2>
        {_line_svg(equity, "Equity Points", "#1f6feb")}
      </div>
      <div class="panel">
        <h2>回撤曲线</h2>
        {_line_svg(drawdown, "Drawdown Points", "#b42318")}
      </div>
    </section>

    <section class="panel">
      <h2>月度收益点数</h2>
      {_bar_svg(monthly)}
    </section>

    <section class="panel">
      <h2>Top 参数组合</h2>
      <div class="scroll">
        {_top_table(top)}
      </div>
    </section>

    <section class="panel">
      <h2>最佳参数交易明细</h2>
      <div class="scroll">
        {_trades_table(trades)}
      </div>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _metric(label: str, value: str, raw: object) -> str:
    css = "positive" if float(raw) >= 0 else "negative"
    return f'<div class="panel metric"><div class="label">{escape(label)}</div><div class="value {css}">{escape(value)}</div></div>'


def _excluded_dates_note(summary: dict[str, object]) -> str:
    excluded = summary.get("excluded_dates") or []
    if not excluded:
        return ""
    dates = ", ".join(str(item) for item in excluded)
    return f'<div class="subtle">已排除日期：{escape(dates)}</div>'


def _param(label: str, value: object) -> str:
    return f'<div class="param"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'


def _fmt(value: object) -> str:
    number = float(value)
    if abs(number) >= 100:
        return f"{number:,.0f}"
    return f"{number:,.2f}"


def _equity_points(trades: list[Trade]) -> list[float]:
    values = [0.0]
    total = 0.0
    for trade in trades:
        total += trade.pnl_points
        values.append(total)
    return values


def _drawdown_points(equity: list[float]) -> list[float]:
    peak = equity[0] if equity else 0.0
    values = []
    for value in equity:
        peak = max(peak, value)
        values.append(peak - value)
    return values


def _monthly_points(trades: list[Trade]) -> list[tuple[str, float]]:
    buckets: dict[str, float] = defaultdict(float)
    for trade in trades:
        key = datetime.fromisoformat(trade.exit_time).strftime("%Y-%m")
        buckets[key] += trade.pnl_points
    return sorted(buckets.items())


def _line_svg(values: list[float], label: str, color: str) -> str:
    if len(values) < 2:
        return '<div class="subtle">没有足够数据绘制图表。</div>'
    width = 900
    height = 280
    pad = 34
    low = min(values)
    high = max(values)
    if high == low:
        high += 1.0
        low -= 1.0
    points = []
    for index, value in enumerate(values):
        x = pad + (width - pad * 2) * index / (len(values) - 1)
        y = height - pad - (height - pad * 2) * (value - low) / (high - low)
        points.append(f"{x:.1f},{y:.1f}")
    zero_y = height - pad - (height - pad * 2) * (0 - low) / (high - low)
    zero_line = ""
    if pad <= zero_y <= height - pad:
        zero_line = f'<line x1="{pad}" y1="{zero_y:.1f}" x2="{width - pad}" y2="{zero_y:.1f}" stroke="#b8c0cc" stroke-dasharray="4 4"/>'
    return f"""
<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>
  <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}" stroke="#c9d1dc"/>
  <line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="#c9d1dc"/>
  {zero_line}
  <polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2.5"/>
  <text x="{pad}" y="20" font-size="12" fill="#646b76">max {high:.2f}</text>
  <text x="{pad}" y="{height - 8}" font-size="12" fill="#646b76">min {low:.2f}</text>
</svg>
"""


def _bar_svg(monthly: list[tuple[str, float]]) -> str:
    if not monthly:
        return '<div class="subtle">没有月度收益数据。</div>'
    width = 1000
    height = 300
    pad = 38
    values = [item[1] for item in monthly]
    low = min(0.0, min(values))
    high = max(0.0, max(values))
    if high == low:
        high += 1.0
        low -= 1.0
    zero_y = height - pad - (height - pad * 2) * (0 - low) / (high - low)
    band = (width - pad * 2) / len(monthly)
    bars = []
    labels = []
    for index, (month, value) in enumerate(monthly):
        x = pad + band * index + band * 0.16
        bar_width = max(2.0, band * 0.68)
        y = height - pad - (height - pad * 2) * (value - low) / (high - low)
        top = min(y, zero_y)
        bar_height = max(1.0, abs(zero_y - y))
        color = "#137b47" if value >= 0 else "#b42318"
        bars.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}"/>')
        if index % max(1, len(monthly) // 8) == 0:
            labels.append(f'<text x="{x:.1f}" y="{height - 8}" font-size="11" fill="#646b76">{escape(month)}</text>')
    return f"""
<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Monthly returns">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>
  <line x1="{pad}" y1="{zero_y:.1f}" x2="{width - pad}" y2="{zero_y:.1f}" stroke="#8c96a3"/>
  {"".join(bars)}
  {"".join(labels)}
  <text x="{pad}" y="20" font-size="12" fill="#646b76">max {high:.2f}</text>
  <text x="{pad}" y="{height - 22}" font-size="12" fill="#646b76">min {low:.2f}</text>
</svg>
"""


def _top_table(top_rows: object) -> str:
    rows = list(top_rows) if isinstance(top_rows, list) else []
    header = """
<table>
  <thead>
    <tr>
      <th>#</th><th>Fast</th><th>Slow</th><th>Time</th><th>SL</th><th>Cooldown</th>
      <th>Score</th><th>Net</th><th>DD</th><th>PF</th><th>Win</th><th>Trades</th>
    </tr>
  </thead>
  <tbody>
"""
    body = []
    for index, row in enumerate(rows, 1):
        body.append(
            f"<tr><td>{index}</td><td>{row['ema_fast']}</td><td>{row['ema_slow']}</td>"
            f"<td>{row['time_check_minutes']}</td><td>{row['stop_loss_points']}</td>"
            f"<td>{row['cooldown_minutes']}</td><td>{_fmt(row['score'])}</td>"
            f"<td>{_fmt(row['net_points'])}</td><td>{_fmt(row['max_drawdown_points'])}</td>"
            f"<td>{_fmt(row['profit_factor'])}</td><td>{float(row['win_rate']) * 100:.1f}%</td>"
            f"<td>{row['trade_count']}</td></tr>"
        )
    return header + "".join(body) + "</tbody></table>"


def _trades_table(trades: list[Trade]) -> str:
    header = """
<table>
  <thead>
    <tr>
      <th>#</th><th>Side</th><th>Entry</th><th>Exit</th><th>Entry Price</th><th>Exit Price</th>
      <th>PnL Points</th><th>Reason</th><th>Bars Held</th>
    </tr>
  </thead>
  <tbody>
"""
    body = []
    for index, trade in enumerate(trades, 1):
        css = "positive" if trade.pnl_points >= 0 else "negative"
        body.append(
            f"<tr><td>{index}</td><td>{trade.side}</td><td>{escape(trade.entry_time)}</td>"
            f"<td>{escape(trade.exit_time)}</td><td>{trade.entry_price:.2f}</td>"
            f"<td>{trade.exit_price:.2f}</td><td class=\"{css}\">{trade.pnl_points:.2f}</td>"
            f"<td>{escape(trade.exit_reason)}</td><td>{trade.bars_held}</td></tr>"
        )
    return header + "".join(body) + "</tbody></table>"


def write_full_optimizer_report(
    path: Path,
    phase1_summary: dict[str, object],
    phase2_results: list[dict[str, object]],
    phase3_results: list[dict[str, object]],
    final_best: dict[str, object],
    wf_windows: list[dict[str, str]],
) -> None:
    """生成三阶段全自动优化综合报告。

    Args:
        phase1_summary: K 线网格搜索结果（同 optimizer 返回的 summary 格式）
        phase2_results: Walk-Forward 验证结果列表，每个元素含候选参数 + 各窗口 IS/OOS 指标
        phase3_results: Tick 级验证结果列表，每个元素含候选参数 + tick 回测指标
        final_best: 最终推荐参数及指标
        wf_windows: Walk-Forward 窗口定义（train_start, train_end, test_start, test_end）
    """
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TimeProfitEA Full Optimization Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17191c;
      --muted: #646b76;
      --line: #d9dee7;
      --good: #137b47;
      --bad: #b42318;
      --blue: #1f6feb;
      --amber: #9a6700;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", Arial, sans-serif;
      line-height: 1.45;
    }}
    header {{
      background: #1d232f;
      color: #fff;
      padding: 24px 28px;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 24px; }}
    h2 {{ font-size: 18px; margin-bottom: 14px; }}
    h3 {{ font-size: 15px; margin-bottom: 10px; }}
    .subtle {{ color: #d4d9e2; margin-top: 6px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 18px;
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .metric .value {{
      font-size: 24px;
      font-weight: 650;
      white-space: nowrap;
    }}
    .positive {{ color: var(--good); }}
    .negative {{ color: var(--bad); }}
    .highlight {{
      border: 2px solid var(--blue);
      background: #f0f6ff;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 7px;
      text-align: right;
      white-space: nowrap;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #fafbfc;
    }}
    .scroll {{ overflow-x: auto; }}
    .params {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }}
    .param {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfe;
    }}
    .param span {{ display: block; color: var(--muted); font-size: 12px; }}
    .param strong {{ display: block; font-size: 20px; margin-top: 2px; }}
    .phase {{ margin-top: 28px; }}
    .phase-title {{
      font-size: 16px;
      color: var(--blue);
      border-bottom: 2px solid var(--blue);
      padding-bottom: 6px;
      margin-bottom: 16px;
    }}
    @media (max-width: 860px) {{
      main {{ padding: 14px; }}
      .grid, .params {{ grid-template-columns: 1fr; }}
      header {{ padding: 20px 16px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>TimeProfitEA 三阶段全自动优化报告</h1>
    <div class="subtle">数据窗口：{escape(str(phase1_summary["from"]))} 至 {escape(str(phase1_summary["to"]))}，Bars：{phase1_summary["bars_used"]}</div>
  </header>
  <main>

    <!-- 最终推荐参数 -->
    <section class="panel highlight">
      <h2>🏆 最终推荐参数（Tick 级验证最优）</h2>
      <div class="params">
        {_param("EMA 快线", final_best["ema_fast"])}
        {_param("EMA 慢线", final_best["ema_slow"])}
        {_param("时间止盈分钟", final_best["time_check_minutes"])}
        {_param("止损点数", final_best["stop_loss_points"])}
        {_param("冷却分钟", final_best["cooldown_minutes"])}
      </div>
      <div class="grid">
        {_metric("Tick净收益点数", _fmt(final_best["net_points"]), final_best["net_points"])}
        {_metric("Tick最大回撤", _fmt(final_best["max_drawdown_points"]), -float(final_best["max_drawdown_points"]))}
        {_metric("Tick Profit Factor", _fmt(final_best["profit_factor"]), final_best["profit_factor"])}
        {_metric("Tick交易次数", str(final_best["trade_count"]), final_best["trade_count"])}
      </div>
    </section>

    <!-- Phase 1 -->
    <div class="phase">
      <div class="phase-title">Phase 1: K 线网格搜索 (Top 参数)</div>
      <section class="panel">
        <div class="scroll">
          {_top_table(phase1_summary["top"][:20])}
        </div>
      </section>
    </div>

    <!-- Phase 2 Walk-Forward -->
    <div class="phase">
      <div class="phase-title">Phase 2: Walk-Forward 验证</div>
      <section class="panel">
        <p style="color:var(--muted);font-size:13px;">Walk-Forward 窗口定义：</p>
        {_wf_windows_table(wf_windows)}
      </section>
      <section class="panel">
        <h3>候选参数 Walk-Forward IS/OOS 表</h3>
        <div class="scroll">
          {_wf_results_table(phase2_results, wf_windows)}
        </div>
      </section>
    </div>

    <!-- Phase 3 Tick -->
    <div class="phase">
      <div class="phase-title">Phase 3: Tick 级验证</div>
      <section class="panel">
        <div class="scroll">
          {_tick_results_table(phase3_results)}
        </div>
      </section>
    </div>

  </main>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _wf_windows_table(wf_windows: list[dict[str, str]]) -> str:
    rows = []
    for index, window in enumerate(wf_windows, 1):
        rows.append(
            f"<tr><td>{index}</td><td>{escape(window['train_start'])}~{escape(window['train_end'])}</td>"
            f"<td>{escape(window['test_start'])}~{escape(window['test_end'])}</td></tr>"
        )
    return f"""
<table>
  <thead><tr><th>窗口</th><th>训练期 (IS)</th><th>测试期 (OOS)</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""


def _wf_results_table(phase2_results: list[dict[str, object]], wf_windows: list[dict[str, str]]) -> str:
    """生成 Walk-Forward IS/OOS 结果表。每个候选参数一行，每列一个窗口的 OOS net_points。"""
    window_headers = [f"OOS W{i+1}" for i in range(len(wf_windows))]
    header_cols = "<th>#</th><th>Fast</th><th>Slow</th><th>Time</th><th>SL</th><th>Cooldown</th>"
    header_cols += "".join(f"<th>{escape(h)}</th>" for h in window_headers)
    header_cols += "<th>OOS正占比</th><th>稳健度</th>"
    header = f"<table><thead><tr>{header_cols}</tr></thead><tbody>"

    body = []
    for index, result in enumerate(phase2_results, 1):
        cols = (
            f"<td>{index}</td><td>{result['ema_fast']}</td><td>{result['ema_slow']}</td>"
            f"<td>{result['time_check_minutes']}</td><td>{result['stop_loss_points']}</td>"
            f"<td>{result['cooldown_minutes']}</td>"
        )
        # 每个窗口的 OOS net_points
        wf_data = result.get("wf_oos_metrics", [])
        for window_metrics in wf_data:
            net = window_metrics.get("net_points", 0)
            css = "positive" if net >= 0 else "negative"
            cols += f'<td class="{css}">{_fmt(net)}</td>'
        # 稳健度指标
        oos_positive_ratio = result.get("oos_positive_ratio", 0)
        robustness = result.get("robustness_score", 0)
        cols += f"<td>{oos_positive_ratio:.0%}</td><td>{_fmt(robustness)}</td>"
        body.append(f"<tr>{cols}</tr>")

    return header + "".join(body) + "</tbody></table>"


def _tick_results_table(phase3_results: list[dict[str, object]]) -> str:
    """生成 Tick 级验证结果表。"""
    header = """
<table>
  <thead>
    <tr>
      <th>#</th><th>Fast</th><th>Slow</th><th>Time</th><th>SL</th><th>Cooldown</th>
      <th>Tick Net</th><th>Tick DD</th><th>Tick PF</th><th>Tick Win</th><th>Tick Trades</th>
    </tr>
  </thead>
  <tbody>
"""
    body = []
    for index, result in enumerate(phase3_results, 1):
        body.append(
            f"<tr><td>{index}</td><td>{result['ema_fast']}</td><td>{result['ema_slow']}</td>"
            f"<td>{result['time_check_minutes']}</td><td>{result['stop_loss_points']}</td>"
            f"<td>{result['cooldown_minutes']}</td><td>{_fmt(result['net_points'])}</td>"
            f"<td>{_fmt(result['max_drawdown_points'])}</td><td>{_fmt(result['profit_factor'])}</td>"
            f"<td>{float(result['win_rate']) * 100:.1f}%</td><td>{result['trade_count']}</td></tr>"
        )
    return header + "".join(body) + "</tbody></table>"
