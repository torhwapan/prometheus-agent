"""HTML report generation."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Dict, Iterable, Optional

from .models import InspectionResult, ItemAnalysis, SeriesAnalysis, isoformat


SEVERITY_LABELS = {
    "critical": "Critical",
    "warning": "Warning",
    "unknown": "Unknown",
    "info": "Watch",
    "ok": "Healthy",
}


def generate_html_report(result: InspectionResult, output_path: Optional[str] = None) -> str:
    """Generate a readable standalone HTML report."""
    html_text = _render_report(result)
    if output_path:
        Path(output_path).write_text(html_text, encoding="utf-8")
    return html_text


def _render_report(result: InspectionResult) -> str:
    counts = _severity_counts(result.items)
    item_rows = "\n".join(_render_item_row(item) for item in result.items)
    details = "\n".join(_render_item_detail(item) for item in result.items)
    generated_at = html.escape(isoformat(result.generated_at))
    start = html.escape(isoformat(result.start))
    end = html.escape(isoformat(result.end))
    prom_url = html.escape(str(result.metadata.get("prometheus_base_url", "")))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prometheus Inspection Report</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #626f7d;
      --line: #d8dee6;
      --critical: #b42318;
      --critical-bg: #fee4e2;
      --warning: #b54708;
      --warning-bg: #ffefd6;
      --unknown: #4b5563;
      --unknown-bg: #e5e7eb;
      --info: #0b5cad;
      --info-bg: #dbeafe;
      --ok: #067647;
      --ok-bg: #dcfae6;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }}
    header {{
      background: #111827;
      color: #ffffff;
      padding: 28px 32px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      font-weight: 650;
      letter-spacing: 0;
    }}
    .meta {{
      color: #d1d5db;
      display: flex;
      flex-wrap: wrap;
      gap: 10px 22px;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 24px;
      margin-bottom: 3px;
    }}
    .metric span {{
      color: var(--muted);
    }}
    section {{
      margin-bottom: 22px;
    }}
    h2 {{
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .table-wrap {{
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 860px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: #344054;
      background: #f9fafb;
      font-size: 12px;
      text-transform: uppercase;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    .badge {{
      display: inline-block;
      min-width: 68px;
      border-radius: 999px;
      padding: 3px 9px;
      font-weight: 650;
      text-align: center;
      white-space: nowrap;
    }}
    .critical {{ color: var(--critical); background: var(--critical-bg); }}
    .warning {{ color: var(--warning); background: var(--warning-bg); }}
    .unknown {{ color: var(--unknown); background: var(--unknown-bg); }}
    .info {{ color: var(--info); background: var(--info-bg); }}
    .ok {{ color: var(--ok); background: var(--ok-bg); }}
    details {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 10px;
    }}
    summary {{
      cursor: pointer;
      padding: 12px 14px;
      font-weight: 650;
    }}
    .detail-body {{
      border-top: 1px solid var(--line);
      padding: 12px 14px 16px;
    }}
    code {{
      display: block;
      white-space: pre-wrap;
      word-break: break-word;
      background: #f3f4f6;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      color: #111827;
    }}
    .muted {{
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <h1>Prometheus Inspection Report</h1>
    <div class="meta">
      <span>Generated: {generated_at}</span>
      <span>Range: {start} to {end}</span>
      <span>Forecast horizon: {result.forecast_hours:g}h</span>
      <span>Prometheus: {prom_url}</span>
    </div>
  </header>
  <main>
    <section class="summary">
      {_summary_card("Critical", counts["critical"])}
      {_summary_card("Warning", counts["warning"])}
      {_summary_card("Watch", counts["info"])}
      {_summary_card("Unknown", counts["unknown"])}
      {_summary_card("Healthy", counts["ok"])}
    </section>
    <section>
      <h2>Inspection Items</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Item</th>
              <th>Result</th>
              <th>Series</th>
              <th>Worst Series</th>
            </tr>
          </thead>
          <tbody>
            {item_rows}
          </tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>Details</h2>
      {details}
    </section>
  </main>
</body>
</html>
"""


def _summary_card(label: str, count: int) -> str:
    return (
        '<div class="metric">'
        f"<strong>{count}</strong>"
        f"<span>{html.escape(label)}</span>"
        "</div>"
    )


def _render_item_row(item: ItemAnalysis) -> str:
    worst = item.series[0].display_name if item.series else "-"
    return f"""<tr>
  <td>{_severity_badge(item.severity)}</td>
  <td><strong>{html.escape(item.name)}</strong><br><span class="muted">{html.escape(item.description)}</span></td>
  <td>{html.escape(item.summary)}</td>
  <td>{item.checked_series} checked / {item.returned_series} shown</td>
  <td>{html.escape(worst)}</td>
</tr>"""


def _render_item_detail(item: ItemAnalysis) -> str:
    series_rows = "\n".join(_render_series_row(item, series) for series in item.series)
    if not series_rows:
        series_rows = '<tr><td colspan="10">No series details available.</td></tr>'
    return f"""<details open>
  <summary>{_severity_badge(item.severity)} {html.escape(item.name)}</summary>
  <div class="detail-body">
    <p>{html.escape(item.summary)}</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Severity</th>
            <th>Series</th>
            <th>Current</th>
            <th>Forecast</th>
            <th>Avg</th>
            <th>Min</th>
            <th>Max</th>
            <th>P95</th>
            <th>Slope/h</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>{series_rows}</tbody>
      </table>
    </div>
    <p class="muted">PromQL</p>
    <code>{html.escape(item.promql)}</code>
  </div>
</details>"""


def _render_series_row(item: ItemAnalysis, series: SeriesAnalysis) -> str:
    unit = item.unit
    return f"""<tr>
  <td>{_severity_badge(series.severity)}</td>
  <td>{html.escape(series.display_name)}</td>
  <td>{_format_number(series.current, unit)}</td>
  <td>{_format_number(series.forecast, unit)}</td>
  <td>{_format_number(series.average, unit)}</td>
  <td>{_format_number(series.minimum, unit)}</td>
  <td>{_format_number(series.maximum, unit)}</td>
  <td>{_format_number(series.p95, unit)}</td>
  <td>{_format_number(series.slope_per_hour, unit + "/h" if unit else "/h")}</td>
  <td>{html.escape(series.reason)}</td>
</tr>"""


def _severity_badge(severity: str) -> str:
    safe = html.escape(severity)
    label = html.escape(SEVERITY_LABELS.get(severity, severity.title()))
    return f'<span class="badge {safe}">{label}</span>'


def _severity_counts(items: Iterable[ItemAnalysis]) -> Dict[str, int]:
    counts = {"critical": 0, "warning": 0, "unknown": 0, "info": 0, "ok": 0}
    for item in items:
        counts[item.severity] = counts.get(item.severity, 0) + 1
    return counts


def _format_number(value: Optional[float], unit: str = "") -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    if abs(value) >= 100:
        text = f"{value:.1f}"
    elif abs(value) >= 10:
        text = f"{value:.2f}"
    else:
        text = f"{value:.3f}"
    return html.escape(f"{text}{unit}")
