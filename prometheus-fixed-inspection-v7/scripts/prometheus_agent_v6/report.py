"""Fixed HTML report rendering for V6."""

from __future__ import annotations

import html
from typing import Any, Dict, Mapping, Sequence


def render_html(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary", {})
    discovery = payload.get("discovery", {})
    findings = payload.get("findings", [])
    packs = payload.get("selected_packs", [])
    ai_summary = payload.get("ai_summary")
    warnings = payload.get("warnings", [])

    rows = "".join(_finding_row(item) for item in findings)
    pack_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('title') or ''))}</td>"
        f"<td>{html.escape(str(item.get('job') or ''))}</td>"
        f"<td>{html.escape(str(item.get('metric_count') or 0))}</td>"
        f"<td>{html.escape(str(item.get('description') or ''))}</td>"
        "</tr>"
        for item in packs
    )
    warning_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prometheus 固定巡检报告</title>
  <style>
    :root {{
      --bg: #f3f5f8;
      --panel: #ffffff;
      --ink: #1f2937;
      --muted: #667085;
      --line: #d0d5dd;
      --accent: #0f766e;
      --critical: #b42318;
      --critical-bg: #fee4e2;
      --warning: #b54708;
      --warning-bg: #ffefd5;
      --info: #175cd3;
      --info-bg: #dbeafe;
      --ok: #067647;
      --ok-bg: #dcfae6;
      --unknown: #475467;
      --unknown-bg: #e4e7ec;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 24rem),
        linear-gradient(180deg, #eef5f3 0%, var(--bg) 18rem);
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    .page {{ max-width: 1360px; margin: 0 auto; padding: 32px 24px 48px; }}
    .hero {{
      background: linear-gradient(135deg, #0f172a, #134e4a);
      color: #fff;
      border-radius: 20px;
      padding: 28px 32px;
      box-shadow: 0 20px 60px rgba(15, 23, 42, 0.18);
    }}
    .hero h1 {{ margin: 0 0 8px; font-size: 30px; }}
    .hero p {{ margin: 0; color: rgba(255,255,255,0.82); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 18px;
      padding: 18px 20px;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
    }}
    .card strong {{ display: block; font-size: 28px; margin-top: 6px; }}
    .section {{
      margin-top: 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
    }}
    .section h2 {{ margin: 0 0 14px; font-size: 20px; }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .meta-item {{
      background: #f8fafc;
      border: 1px solid #e4e7ec;
      border-radius: 14px;
      padding: 14px 16px;
    }}
    .meta-item .label {{ color: var(--muted); font-size: 13px; }}
    .meta-item .value {{ margin-top: 6px; word-break: break-all; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid #e4e7ec;
      padding: 12px 10px;
      vertical-align: top;
      text-align: left;
    }}
    th {{
      background: #f8fafc;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    tr:last-child td {{ border-bottom: none; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
    }}
    .critical {{ color: var(--critical); background: var(--critical-bg); }}
    .warning {{ color: var(--warning); background: var(--warning-bg); }}
    .info {{ color: var(--info); background: var(--info-bg); }}
    .ok {{ color: var(--ok); background: var(--ok-bg); }}
    .unknown {{ color: var(--unknown); background: var(--unknown-bg); }}
    .mono {{ font-family: Consolas, "Courier New", monospace; font-size: 12px; }}
    .muted {{ color: var(--muted); }}
    ul {{ margin: 0; padding-left: 20px; }}
    @media (max-width: 840px) {{
      .page {{ padding: 20px 14px 32px; }}
      .hero {{ padding: 22px 20px; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>Prometheus 固定巡检报告</h1>
      <p>生成时间: {html.escape(str(payload.get("generated_at") or ""))}</p>
      <div class="grid">
        <div class="card"><span class="muted">总体等级</span><strong>{html.escape(str(summary.get("severity") or "unknown"))}</strong></div>
        <div class="card"><span class="muted">巡检 pack 数</span><strong>{html.escape(str(summary.get("pack_count") or 0))}</strong></div>
        <div class="card"><span class="muted">发现项总数</span><strong>{html.escape(str(summary.get("finding_count") or 0))}</strong></div>
        <div class="card"><span class="muted">活跃 target 数</span><strong>{html.escape(str(discovery.get("active_target_count") or 0))}</strong></div>
      </div>
    </section>

    <section class="section">
      <h2>巡检范围</h2>
      <div class="meta">
        <div class="meta-item">
          <div class="label">Prometheus 地址</div>
          <div class="value mono">{html.escape(str(payload.get("prometheus_url") or ""))}</div>
        </div>
        <div class="meta-item">
          <div class="label">实例过滤</div>
          <div class="value">{html.escape(str(payload.get("instance_filter") or "未指定"))}</div>
        </div>
        <div class="meta-item">
          <div class="label">发现到的 Job</div>
          <div class="value">{html.escape(", ".join(discovery.get("normalized_jobs", [])) or "无")}</div>
        </div>
        <div class="meta-item">
          <div class="label">统计汇总</div>
          <div class="value">
            critical={html.escape(str(summary.get("counts", {}).get("critical", 0)))},
            warning={html.escape(str(summary.get("counts", {}).get("warning", 0)))},
            info={html.escape(str(summary.get("counts", {}).get("info", 0)))},
            ok={html.escape(str(summary.get("counts", {}).get("ok", 0)))},
            unknown={html.escape(str(summary.get("counts", {}).get("unknown", 0)))}
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>固定巡检 Pack</h2>
      <table>
        <thead>
          <tr><th>Pack</th><th>Job</th><th>指标数</th><th>说明</th></tr>
        </thead>
        <tbody>{pack_rows}</tbody>
      </table>
    </section>

    <section class="section">
      <h2>分析结论</h2>
      {_ai_summary_html(ai_summary)}
      {_warnings_html(warning_html)}
      <table>
        <thead>
          <tr>
            <th>等级</th>
            <th>Pack</th>
            <th>Job / Instance</th>
            <th>指标</th>
            <th>当前值</th>
            <th>规则分析</th>
            <th>AI 补充</th>
            <th>标签</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
  </div>
</body>
</html>"""


def _finding_row(item: Mapping[str, Any]) -> str:
    labels = item.get("labels", {})
    label_text = ", ".join(f"{key}={value}" for key, value in sorted(labels.items()))
    unit = ""
    if isinstance(item.get("analysis"), Mapping):
        unit = str(item["analysis"].get("unit") or "")
    return (
        "<tr>"
        f"<td>{_badge(str(item.get('severity') or 'unknown'))}</td>"
        f"<td>{html.escape(str(item.get('pack_title') or ''))}</td>"
        f"<td><div>{html.escape(str(item.get('job') or ''))}</div><div class=\"muted\">{html.escape(str(item.get('instance') or ''))}</div></td>"
        f"<td><div>{html.escape(str(item.get('metric_name') or item.get('metric_id') or ''))}</div><div class=\"muted mono\">{html.escape(str(item.get('metric_id') or ''))}</div></td>"
        f"<td>{html.escape(_format_value(item.get('current_value'), unit))}</td>"
        f"<td>{html.escape(str(item.get('reason') or ''))}</td>"
        f"<td>{html.escape(str(item.get('ai_comment') or ''))}</td>"
        f"<td class=\"mono\">{html.escape(label_text)}</td>"
        "</tr>"
    )


def _ai_summary_html(ai_summary: Any) -> str:
    if not ai_summary:
        return ""
    return f"<p><strong>AI 补充摘要:</strong> {html.escape(str(ai_summary))}</p>"


def _warnings_html(items_html: str) -> str:
    if not items_html:
        return ""
    return f"<div class=\"meta-item\" style=\"margin-bottom: 16px;\"><div class=\"label\">补充说明</div><ul>{items_html}</ul></div>"


def _format_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 100:
        text = f"{number:.1f}"
    elif abs(number) >= 10:
        text = f"{number:.2f}"
    else:
        text = f"{number:.3f}"
    return f"{text}{unit}"


def _badge(severity: str) -> str:
    return f'<span class="badge {html.escape(severity)}">{html.escape(severity)}</span>'
