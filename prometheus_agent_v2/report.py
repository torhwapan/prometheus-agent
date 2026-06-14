"""Markdown and HTML report rendering for v2."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Sequence


def render_markdown(analysis: Mapping[str, Any], ai_correlation: Mapping[str, Any] | None = None) -> str:
    lines = [
        "# Prometheus 巡检报告",
        "",
        f"- 生成时间: {datetime.now(timezone.utc).isoformat()}",
        f"- 总体等级: {analysis.get('severity', 'unknown')}",
        f"- 统计: {analysis.get('counts', {})}",
        "",
    ]
    if ai_correlation:
        lines.extend(["## AI 关联性分析", "", str(ai_correlation.get("summary", "")), ""])
        for item in ai_correlation.get("correlations", []):
            lines.append(f"- `{item.get('level')}` {item.get('job')}/{item.get('instance')}: {item.get('reason')}；建议：{item.get('suggestion')}")
        lines.append("")

    grouped = _group_items(analysis.get("items", []))
    for job, instances in grouped.items():
        lines.extend([f"## Job: {job}", ""])
        for instance, items in instances.items():
            lines.extend([f"### Instance: {instance}", ""])
            lines.append("| 等级 | 指标 | 当前值 | 结论 | AI简评 |")
            lines.append("|---|---|---:|---|---|")
            for item in items:
                metric = item.get("metric_name") or item.get("metric_id")
                current = _format_value(item.get("current_value"), item.get("analysis", {}).get("unit", ""))
                lines.append(
                    f"| {item.get('severity')} | {metric} | {current} | {item.get('reason')} | {item.get('ai_comment') or ''} |"
                )
            lines.append("")
    return "\n".join(lines)


def render_html(analysis: Mapping[str, Any], ai_correlation: Mapping[str, Any] | None = None) -> str:
    markdown = render_markdown(analysis, ai_correlation=ai_correlation)
    rows = []
    for item in analysis.get("items", []):
        unit = item.get("analysis", {}).get("unit", "")
        rows.append(
            "<tr>"
            f"<td>{_badge(str(item.get('severity') or 'unknown'))}</td>"
            f"<td>{html.escape(str(item.get('job') or ''))}</td>"
            f"<td>{html.escape(str(item.get('instance') or ''))}</td>"
            f"<td>{html.escape(str(item.get('metric_name') or item.get('metric_id') or ''))}</td>"
            f"<td>{html.escape(_format_value(item.get('current_value'), unit))}</td>"
            f"<td>{html.escape(str(item.get('reason') or ''))}</td>"
            f"<td>{html.escape(str(item.get('ai_comment') or ''))}</td>"
            "</tr>"
        )
    correlation_html = ""
    if ai_correlation:
        correlation_html = (
            "<section><h2>AI 关联性分析</h2>"
            f"<p>{html.escape(str(ai_correlation.get('summary') or ''))}</p></section>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prometheus 巡检报告</title>
  <style>
    body {{ margin: 0; background: #f6f7f9; color: #1f2933; font-family: Arial, sans-serif; }}
    header {{ background: #111827; color: #fff; padding: 24px 32px; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee6; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee6; text-align: left; vertical-align: top; }}
    th {{ background: #f9fafb; font-size: 12px; text-transform: uppercase; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-weight: 700; }}
    .critical {{ color: #b42318; background: #fee4e2; }}
    .warning {{ color: #b54708; background: #ffefd6; }}
    .info {{ color: #0b5cad; background: #dbeafe; }}
    .ok {{ color: #067647; background: #dcfae6; }}
    .unknown {{ color: #4b5563; background: #e5e7eb; }}
    pre {{ white-space: pre-wrap; background: #fff; border: 1px solid #d8dee6; padding: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>Prometheus 巡检报告</h1>
    <p>总体等级: {html.escape(str(analysis.get('severity', 'unknown')))} | 统计: {html.escape(str(analysis.get('counts', {})))}</p>
  </header>
  <main>
    {correlation_html}
    <section>
      <h2>指标明细</h2>
      <table>
        <thead><tr><th>等级</th><th>Job</th><th>Instance</th><th>指标</th><th>当前值</th><th>规则分析</th><th>AI简评</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    <section>
      <h2>Markdown 原文</h2>
      <pre>{html.escape(markdown)}</pre>
    </section>
  </main>
</body>
</html>"""


def _group_items(items: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, list]]:
    grouped: Dict[str, Dict[str, list]] = {}
    for item in items:
        job = str(item.get("job") or "unknown")
        instance = str(item.get("instance") or "unknown")
        grouped.setdefault(job, {}).setdefault(instance, []).append(item)
    return grouped


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
