"""Executive-style HTML report rendering for Prometheus agent v4."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Dict, List, Mapping, Sequence, Tuple


SEVERITY_LABELS = {
    "critical": "高危",
    "warning": "预警",
    "info": "关注",
    "ok": "正常",
    "unknown": "未知",
}

SEVERITY_ORDER = {
    "critical": 4,
    "warning": 3,
    "info": 2,
    "unknown": 1,
    "ok": 0,
}


def render_html_report(
    analysis: Mapping[str, Any],
    *,
    plan: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    ai_correlation: Mapping[str, Any] | None = None,
    ai_batch_outputs: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    enriched_items = _enrich_items(analysis.get("items", []), ai_batch_outputs or [])
    counts = _normalize_counts(analysis.get("counts"))
    total = len(enriched_items)
    risky_items = [item for item in enriched_items if str(item.get("severity") or "unknown") != "ok"]
    top_risks = sorted(risky_items, key=_item_sort_key, reverse=True)[:8]
    grouped = _group_items(enriched_items)
    job_count = len({str(item.get("job") or "unknown") for item in enriched_items})
    instance_count = len({str(item.get("instance") or "unknown") for item in enriched_items})
    correlation_cards = _correlation_cards(ai_correlation)
    report_time = _format_now()
    plan = plan or {}
    meta = meta or {}

    executive_summary = _build_executive_summary(
        analysis=analysis,
        total=total,
        risky_count=len(risky_items),
        ai_correlation=ai_correlation,
    )

    detail_sections = []
    for job, instances in grouped:
        detail_sections.append(_render_job_section(job, instances))

    risk_rows = [_render_risk_row(item) for item in top_risks]

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prometheus 巡检报告</title>
  <style>
    :root {{
      --bg: #eef4f8;
      --bg-accent: #f8fbfd;
      --surface: #ffffff;
      --surface-alt: #f4f8fb;
      --text: #17324d;
      --muted: #5f7488;
      --line: #d6e2ec;
      --shadow: 0 18px 48px rgba(19, 50, 77, 0.08);
      --critical: #b42318;
      --critical-bg: #fde7e4;
      --warning: #c46b00;
      --warning-bg: #fff1db;
      --info: #0b5cad;
      --info-bg: #deecff;
      --ok: #0f7b52;
      --ok-bg: #dcf5e8;
      --unknown: #667085;
      --unknown-bg: #edf0f3;
      --hero-start: #163b63;
      --hero-end: #1e6f8b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
      background:
        radial-gradient(circle at top right, rgba(30, 111, 139, 0.18), transparent 22%),
        linear-gradient(180deg, #f7fbfe 0%, var(--bg) 100%);
    }}
    .page {{ max-width: 1360px; margin: 0 auto; padding: 28px 24px 56px; }}
    .hero {{
      padding: 30px 32px;
      border-radius: 22px;
      color: #fff;
      background: linear-gradient(135deg, var(--hero-start), var(--hero-end));
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -40px -55px auto;
      width: 260px;
      height: 260px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.08);
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.12);
      font-size: 13px;
    }}
    h1 {{ margin: 16px 0 10px; font-size: 34px; line-height: 1.15; }}
    .hero p {{ margin: 0; max-width: 900px; color: rgba(255, 255, 255, 0.88); line-height: 1.7; }}
    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .hero-tag {{
      display: inline-flex;
      align-items: center;
      padding: 8px 12px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.12);
      color: #fff;
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-top: 22px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid rgba(214, 226, 236, 0.85);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 20px;
    }}
    .metric-card {{
      min-height: 132px;
      background:
        linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(248,251,253,0.95) 100%);
    }}
    .metric-card .label {{ color: var(--muted); font-size: 13px; margin-bottom: 10px; }}
    .metric-card .value {{ font-size: 34px; font-weight: 700; line-height: 1; }}
    .metric-card .sub {{ margin-top: 10px; color: var(--muted); font-size: 13px; }}
    .section {{
      margin-top: 22px;
      padding: 22px;
      border-radius: 18px;
      background: var(--surface);
      border: 1px solid rgba(214, 226, 236, 0.85);
      box-shadow: var(--shadow);
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 16px;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
    }}
    .section-head p {{
      margin: 6px 0 0;
      color: var(--muted);
      line-height: 1.65;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
      white-space: nowrap;
    }}
    .critical {{ color: var(--critical); background: var(--critical-bg); }}
    .warning {{ color: var(--warning); background: var(--warning-bg); }}
    .info {{ color: var(--info); background: var(--info-bg); }}
    .ok {{ color: var(--ok); background: var(--ok-bg); }}
    .unknown {{ color: var(--unknown); background: var(--unknown-bg); }}
    .summary-layout {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 18px;
    }}
    .summary-box {{
      background: var(--surface-alt);
      border-radius: 16px;
      border: 1px solid var(--line);
      padding: 18px;
    }}
    .summary-box h3 {{
      margin: 0 0 12px;
      font-size: 16px;
    }}
    .summary-box p, .summary-box li {{
      color: var(--text);
      line-height: 1.7;
    }}
    .summary-box ul, .summary-box ol {{
      margin: 0;
      padding-left: 20px;
    }}
    .count-list {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .count-item {{
      padding: 12px 14px;
      border-radius: 14px;
      background: #fff;
      border: 1px solid var(--line);
    }}
    .count-item strong {{
      display: block;
      margin-bottom: 4px;
      font-size: 22px;
      line-height: 1;
    }}
    .risk-table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 16px;
    }}
    .risk-table thead th {{
      background: #eaf2f8;
      color: #30506f;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .risk-table th, .risk-table td {{
      padding: 14px 14px;
      vertical-align: top;
      text-align: left;
      border-bottom: 1px solid var(--line);
    }}
    .risk-table tr:last-child td {{ border-bottom: none; }}
    .metric-name {{
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .metric-id {{
      color: var(--muted);
      font-size: 12px;
    }}
    .muted {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .chip {{
      display: inline-flex;
      padding: 4px 8px;
      border-radius: 999px;
      background: #eef4f8;
      color: #33536f;
      font-size: 12px;
    }}
    .callout {{
      padding: 16px 18px;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(30, 111, 139, 0.09), rgba(22, 59, 99, 0.03));
      border: 1px solid rgba(30, 111, 139, 0.18);
    }}
    .callout p:last-child {{ margin-bottom: 0; }}
    .correlation-list {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 16px;
    }}
    .correlation-card {{
      padding: 18px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: var(--surface-alt);
    }}
    .correlation-card h3 {{
      margin: 10px 0 10px;
      font-size: 17px;
      line-height: 1.4;
    }}
    .correlation-card p {{
      margin: 0 0 8px;
      line-height: 1.7;
    }}
    .instance-section {{
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--surface-alt);
      margin-top: 14px;
      overflow: hidden;
    }}
    .instance-section summary {{
      list-style: none;
      cursor: pointer;
      padding: 16px 18px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      background: rgba(255, 255, 255, 0.75);
    }}
    .instance-section summary::-webkit-details-marker {{ display: none; }}
    .instance-title {{
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .instance-meta {{
      color: var(--muted);
      font-size: 13px;
    }}
    .instance-body {{
      padding: 0 18px 18px;
    }}
    .detail-table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid var(--line);
    }}
    .detail-table th, .detail-table td {{
      padding: 12px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    .detail-table th {{
      background: #eef5fa;
      font-size: 12px;
      color: #35536f;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .detail-table tr:last-child td {{ border-bottom: none; }}
    .progress {{
      width: 120px;
      height: 8px;
      border-radius: 999px;
      background: #e6edf3;
      overflow: hidden;
      margin-top: 8px;
    }}
    .progress > span {{
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #3b82f6, #1f8b7b);
    }}
    .text-block p {{
      margin: 0 0 8px;
      line-height: 1.7;
    }}
    .text-block ul, .text-block ol {{
      margin: 0 0 8px;
      padding-left: 20px;
      line-height: 1.7;
    }}
    .text-block code {{
      padding: 1px 6px;
      border-radius: 8px;
      background: rgba(19, 50, 77, 0.08);
      font-family: Consolas, monospace;
      font-size: 0.92em;
    }}
    .empty {{
      padding: 18px;
      border: 1px dashed var(--line);
      border-radius: 16px;
      color: var(--muted);
      background: #fbfdff;
      line-height: 1.7;
    }}
    @media (max-width: 1100px) {{
      .grid, .summary-layout, .correlation-list {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 860px) {{
      .page {{ padding: 18px 14px 36px; }}
      .hero {{ padding: 24px 20px; border-radius: 18px; }}
      h1 {{ font-size: 28px; }}
      .grid, .summary-layout, .correlation-list {{ grid-template-columns: 1fr; }}
      .risk-table, .detail-table {{ display: block; overflow-x: auto; }}
      .section {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="eyebrow">Prometheus Inspection Report</div>
      <h1>Prometheus 巡检报告</h1>
      <p>{html.escape(executive_summary)}</p>
      <div class="hero-meta">
        <span class="hero-tag">Prometheus: {html.escape(_display_prometheus(plan.get("prometheus_url")))}</span>
        <span class="hero-tag">巡检范围: {html.escape(_display_scope(plan.get("job"), plan.get("instance")))}</span>
        <span class="hero-tag">时间窗口: {html.escape(_display_time_window(plan))}</span>
        <span class="hero-tag">生成时间: {html.escape(report_time)}</span>
      </div>
    </section>

    <section class="grid">
      <div class="card metric-card">
        <div class="label">总体风险等级</div>
        <div class="value">{html.escape(SEVERITY_LABELS.get(str(analysis.get("severity") or "unknown"), "未知"))}</div>
        <div class="sub">{_badge(str(analysis.get("severity") or "unknown"))}</div>
      </div>
      <div class="card metric-card">
        <div class="label">重点关注指标</div>
        <div class="value">{len(risky_items)}</div>
        <div class="sub">总指标 {total} 项</div>
      </div>
      <div class="card metric-card">
        <div class="label">巡检对象</div>
        <div class="value">{job_count}</div>
        <div class="sub">Job 数量 / 实例数 {instance_count}</div>
      </div>
      <div class="card metric-card">
        <div class="label">高优先风险</div>
        <div class="value">{counts["critical"] + counts["warning"]}</div>
        <div class="sub">高危 {counts["critical"]} / 预警 {counts["warning"]}</div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>执行摘要</h2>
          <p>这一部分面向汇报场景，优先说明整体风险、重点指标和建议关注方向。</p>
        </div>
      </div>
      <div class="summary-layout">
        <div class="summary-box text-block">{_render_text_block(ai_correlation.get("summary") if isinstance(ai_correlation, Mapping) else executive_summary)}</div>
        <div class="summary-box">
          <h3>风险统计</h3>
          <div class="count-list">
            {_render_count_item("高危", counts["critical"], "critical")}
            {_render_count_item("预警", counts["warning"], "warning")}
            {_render_count_item("关注", counts["info"], "info")}
            {_render_count_item("正常", counts["ok"], "ok")}
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>重点风险指标</h2>
          <p>仅展示非正常指标，适合领导快速定位需要关注的系统和实例。</p>
        </div>
      </div>
      {('<table class="risk-table"><thead><tr><th>等级</th><th>指标</th><th>对象</th><th>当前值</th><th>固定策略分析</th><th>AI 分析</th><th>建议动作</th></tr></thead><tbody>' + ''.join(risk_rows) + '</tbody></table>') if risk_rows else '<div class="empty">本次巡检没有发现需要重点汇报的异常指标。</div>'}
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>关联分析</h2>
          <p>汇总多个指标之间的关联现象，帮助解释为什么当前实例需要优先关注。</p>
        </div>
      </div>
      <div class="callout text-block">{_render_text_block(ai_correlation.get("summary") if isinstance(ai_correlation, Mapping) else "暂无 AI 关联分析结论。")}</div>
      {('<div class="correlation-list">' + ''.join(correlation_cards) + '</div>') if correlation_cards else '<div class="empty" style="margin-top:16px;">暂无跨指标关联风险结论。</div>'}
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>分组明细</h2>
          <p>按照 job 和 instance 逐层展开。重点风险默认展开，正常项收拢，兼顾汇报和排查。</p>
        </div>
      </div>
      {''.join(detail_sections) if detail_sections else '<div class="empty">没有可展示的指标明细。</div>'}
    </section>
  </div>
</body>
</html>"""


def _enrich_items(
    items: Sequence[Mapping[str, Any]],
    ai_batch_outputs: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    findings_by_metric: Dict[Tuple[str, str, str], List[Mapping[str, Any]]] = {}
    batch_summary_by_scope: Dict[Tuple[str, str], str] = {}
    for payload in ai_batch_outputs:
        normalized = _normalize_batch_payload(payload)
        if not normalized:
            continue
        job = str(normalized.get("job") or "")
        instance = str(normalized.get("instance") or "")
        summary = str(normalized.get("summary") or "").strip()
        if summary:
            batch_summary_by_scope[(job, instance)] = summary
        for finding in normalized.get("findings", []):
            if not isinstance(finding, Mapping):
                continue
            metric_ids = finding.get("metrics") if isinstance(finding.get("metrics"), list) else []
            for metric_id in metric_ids:
                key = (job, instance, str(metric_id))
                findings_by_metric.setdefault(key, []).append(finding)

    enriched = []
    for raw in items:
        item = dict(raw)
        job = str(item.get("job") or "")
        instance = str(item.get("instance") or "")
        metric_id = str(item.get("metric_id") or "")
        metric_findings = findings_by_metric.get((job, instance, metric_id), [])
        ai_summary = batch_summary_by_scope.get((job, instance))
        if metric_findings:
            primary = metric_findings[0]
            item["ai_comment"] = primary.get("reason") or primary.get("summary") or ai_summary
            item["ai_suggestion"] = primary.get("suggestion")
            item["ai_findings"] = metric_findings
        elif ai_summary and not item.get("ai_comment"):
            item["ai_comment"] = ai_summary
        enriched.append(item)
    return enriched


def _normalize_batch_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(payload.get("finding"), Mapping):
        finding = payload.get("finding")
        return {
            "job": finding.get("job") or payload.get("job"),
            "instance": finding.get("instance") or payload.get("instance"),
            "summary": finding.get("summary"),
            "findings": finding.get("findings") if isinstance(finding.get("findings"), list) else [],
        }
    if isinstance(payload.get("findings"), Mapping):
        finding = payload.get("findings")
        return {
            "job": finding.get("job") or payload.get("job"),
            "instance": finding.get("instance") or payload.get("instance"),
            "summary": finding.get("summary"),
            "findings": finding.get("findings") if isinstance(finding.get("findings"), list) else [],
        }
    if isinstance(payload, Mapping):
        return {
            "job": payload.get("job"),
            "instance": payload.get("instance"),
            "summary": payload.get("summary"),
            "findings": payload.get("findings") if isinstance(payload.get("findings"), list) else [],
        }
    return {}


def _normalize_counts(raw: Any) -> Dict[str, int]:
    base = {"critical": 0, "warning": 0, "info": 0, "ok": 0, "unknown": 0}
    if not isinstance(raw, Mapping):
        return base
    for key in base:
        try:
            base[key] = int(raw.get(key, 0))
        except (TypeError, ValueError):
            base[key] = 0
    return base


def _build_executive_summary(
    *,
    analysis: Mapping[str, Any],
    total: int,
    risky_count: int,
    ai_correlation: Mapping[str, Any] | None,
) -> str:
    severity = SEVERITY_LABELS.get(str(analysis.get("severity") or "unknown"), "未知")
    if isinstance(ai_correlation, Mapping):
        summary = str(ai_correlation.get("summary") or "").strip()
        if summary:
            return f"本次巡检共检查 {total} 项指标，其中 {risky_count} 项需要关注。整体风险等级为{severity}。{summary}"
    if risky_count <= 0:
        return f"本次巡检共检查 {total} 项指标，当前未发现需要重点汇报的异常，整体风险等级为{severity}。"
    return f"本次巡检共检查 {total} 项指标，其中 {risky_count} 项需要关注，整体风险等级为{severity}。建议优先查看下方重点风险指标和关联分析。"


def _group_items(items: Sequence[Mapping[str, Any]]) -> List[Tuple[str, List[Tuple[str, List[Mapping[str, Any]]]]]]:
    grouped: Dict[str, Dict[str, List[Mapping[str, Any]]]] = {}
    for item in items:
        job = str(item.get("job") or "unknown")
        instance = str(item.get("instance") or "unknown")
        grouped.setdefault(job, {}).setdefault(instance, []).append(item)

    result = []
    for job, instances in sorted(grouped.items()):
        instance_list = []
        for instance, values in sorted(instances.items(), key=lambda item: _instance_sort_key(item[1]), reverse=True):
            ordered = sorted(values, key=_item_sort_key, reverse=True)
            instance_list.append((instance, ordered))
        result.append((job, instance_list))
    result.sort(key=lambda item: _job_sort_key(item[1]), reverse=True)
    return result


def _job_sort_key(instances: Sequence[Tuple[str, List[Mapping[str, Any]]]]) -> Tuple[int, int]:
    severities = [_severity_rank(str(metric.get("severity") or "unknown")) for _, values in instances for metric in values]
    risky_count = sum(1 for _, values in instances for metric in values if str(metric.get("severity") or "unknown") != "ok")
    return (max(severities) if severities else -1, risky_count)


def _instance_sort_key(items: Sequence[Mapping[str, Any]]) -> Tuple[int, int]:
    severities = [_severity_rank(str(item.get("severity") or "unknown")) for item in items]
    risky_count = sum(1 for item in items if str(item.get("severity") or "unknown") != "ok")
    return (max(severities) if severities else -1, risky_count)


def _item_sort_key(item: Mapping[str, Any]) -> Tuple[int, float]:
    return (_severity_rank(str(item.get("severity") or "unknown")), _abs_number(item.get("current_value")))


def _severity_rank(severity: str) -> int:
    return SEVERITY_ORDER.get(severity, -1)


def _render_job_section(job: str, instances: Sequence[Tuple[str, List[Mapping[str, Any]]]]) -> str:
    risky_count = sum(1 for _, values in instances for item in values if str(item.get("severity") or "unknown") != "ok")
    total = sum(len(values) for _, values in instances)
    blocks = [_render_instance_section(instance, values) for instance, values in instances]
    return (
        '<div style="margin-bottom:20px;">'
        f'<div class="section-head" style="margin-bottom:10px;"><div><h2 style="font-size:18px;">{html.escape(job)}</h2>'
        f'<p>{html.escape(f"共 {len(instances)} 个实例，巡检 {total} 项指标，需关注 {risky_count} 项。")}</p></div></div>'
        f'{"".join(blocks)}'
        "</div>"
    )


def _render_instance_section(instance: str, items: Sequence[Mapping[str, Any]]) -> str:
    risky = [item for item in items if str(item.get("severity") or "unknown") != "ok"]
    top_severity = max((_severity_rank(str(item.get("severity") or "unknown")) for item in items), default=0)
    summary = f"{len(items)} 项指标，需关注 {len(risky)} 项"
    rows = "".join(_render_detail_row(item) for item in items)
    open_attr = " open" if risky or top_severity >= _severity_rank("warning") else ""
    badge = _badge(str(risky[0].get("severity") if risky else "ok"))
    return (
        f'<details class="instance-section"{open_attr}>'
        '<summary>'
        f'<div><div class="instance-title">{html.escape(instance)}</div><div class="instance-meta">{html.escape(summary)}</div></div>'
        f'<div>{badge}</div>'
        "</summary>"
        '<div class="instance-body">'
        '<table class="detail-table">'
        '<thead><tr><th>等级</th><th>指标</th><th>当前值</th><th>趋势 / 阈值</th><th>固定策略分析</th><th>AI 分析</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div></details>"
    )


def _render_risk_row(item: Mapping[str, Any]) -> str:
    analysis = item.get("analysis") if isinstance(item.get("analysis"), Mapping) else {}
    suggestion = _primary_suggestion(item)
    return (
        "<tr>"
        f"<td>{_badge(str(item.get('severity') or 'unknown'))}</td>"
        f"<td><div class='metric-name'>{html.escape(str(item.get('metric_name') or item.get('metric_id') or ''))}</div>"
        f"<div class='metric-id'>{html.escape(str(item.get('metric_id') or ''))}</div>"
        f"<div class='chips'>{''.join(_trend_chips(analysis))}</div></td>"
        f"<td><div>{html.escape(str(item.get('job') or ''))}</div><div class='muted'>{html.escape(str(item.get('instance') or ''))}</div></td>"
        f"<td>{html.escape(_format_value(item.get('current_value'), analysis.get('unit', '')))}{_render_progress(analysis)}</td>"
        f"<td class='text-block'>{_render_text_block(_strategy_text(item))}</td>"
        f"<td class='text-block'>{_render_text_block(item.get('ai_comment') or '无额外 AI 补充。')}</td>"
        f"<td class='text-block'>{_render_text_block(suggestion)}</td>"
        "</tr>"
    )


def _render_detail_row(item: Mapping[str, Any]) -> str:
    analysis = item.get("analysis") if isinstance(item.get("analysis"), Mapping) else {}
    trend_html = "<div class='muted'>" + html.escape(_trend_summary(analysis)) + "</div>" + _render_progress(analysis)
    return (
        "<tr>"
        f"<td>{_badge(str(item.get('severity') or 'unknown'))}</td>"
        f"<td><div class='metric-name'>{html.escape(str(item.get('metric_name') or item.get('metric_id') or ''))}</div>"
        f"<div class='metric-id'>{html.escape(str(item.get('metric_id') or ''))}</div></td>"
        f"<td>{html.escape(_format_value(item.get('current_value'), analysis.get('unit', '')))}</td>"
        f"<td>{trend_html}<div class='chips'>{''.join(_trend_chips(analysis))}</div></td>"
        f"<td class='text-block'>{_render_text_block(_strategy_text(item))}</td>"
        f"<td class='text-block'>{_render_text_block(item.get('ai_comment') or item.get('ai_suggestion') or '无')}</td>"
        "</tr>"
    )


def _correlation_cards(ai_correlation: Mapping[str, Any] | None) -> List[str]:
    if not isinstance(ai_correlation, Mapping):
        return []
    cards = []
    for item in ai_correlation.get("correlations", []):
        if not isinstance(item, Mapping):
            continue
        jobs = ", ".join(str(value) for value in item.get("jobs", []) if value) or "未指定"
        instances = ", ".join(str(value) for value in item.get("instances", []) if value) or "未指定"
        cards.append(
            '<div class="correlation-card">'
            f"{_badge(str(item.get('level') or 'unknown'))}"
            f"<h3>{html.escape(jobs)}</h3>"
            f"<p><strong>涉及实例：</strong>{html.escape(instances)}</p>"
            f"<div class='text-block'>{_render_text_block(item.get('reason'))}</div>"
            f"<div class='text-block'>{_render_text_block(item.get('suggestion') or '建议运维进一步排查相关链路。')}</div>"
            "</div>"
        )
    return cards


def _render_count_item(label: str, value: int, severity: str) -> str:
    return (
        '<div class="count-item">'
        f"<strong>{value}</strong>"
        f"<span>{html.escape(label)}</span> {_badge(severity)}"
        "</div>"
    )


def _display_prometheus(value: Any) -> str:
    text = str(value or "").strip()
    return text or "未指定"


def _display_scope(job: Any, instance: Any) -> str:
    job_text = str(job).strip() if job not in {None, ""} else "全部 Job"
    instance_text = str(instance).strip() if instance not in {None, ""} else "全部 Instance"
    return f"{job_text} / {instance_text}"


def _display_time_window(plan: Mapping[str, Any]) -> str:
    start = _format_time(plan.get("start"))
    end = _format_time(plan.get("end"))
    if start and end:
        return f"{start} - {end}"
    hours = plan.get("range_hours")
    return f"最近 {hours} 小时" if hours else "最近 24 小时"


def _format_time(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return str(value)
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


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


def _render_progress(analysis: Mapping[str, Any]) -> str:
    percent = _progress_percent(analysis)
    if percent is None:
        return ""
    return f'<div class="progress"><span style="width:{percent:.0f}%"></span></div>'


def _progress_percent(analysis: Mapping[str, Any]) -> float | None:
    current = _to_float(analysis.get("current"))
    if current is None:
        return None
    max_value = _to_float(analysis.get("max_value"))
    critical = _to_float(analysis.get("critical"))
    denominator = max_value or critical
    if denominator is None or denominator <= 0:
        return None
    percent = max(min(current / denominator * 100, 100), 0)
    return percent


def _trend_summary(analysis: Mapping[str, Any]) -> str:
    if analysis.get("fallback_current_only"):
        return "范围趋势获取失败，本项仅根据当前值做阈值判断"
    current = _format_value(analysis.get("current"), analysis.get("unit", ""))
    forecast = _format_value(analysis.get("forecast_24h"), analysis.get("unit", "")) if analysis.get("forecast_24h") is not None else "n/a"
    slope = _format_value(analysis.get("slope_per_hour"), analysis.get("unit", "")) if analysis.get("slope_per_hour") is not None else "n/a"
    return f"当前 {current}，24h 预测 {forecast}，每小时变化 {slope}"


def _trend_chips(analysis: Mapping[str, Any]) -> List[str]:
    chips = []
    if analysis.get("fallback_current_only"):
        chips.append('<span class="chip">仅当前值判断</span>')
        if analysis.get("warning") is not None:
            chips.append(f'<span class="chip">{html.escape("阈值告警线 " + _format_value(analysis.get("warning"), analysis.get("unit", "")))}</span>')
        return chips
    if analysis.get("burst"):
        chips.append('<span class="chip">存在突增</span>')
    if analysis.get("sustained_growth"):
        chips.append('<span class="chip">持续增长</span>')
    time_to_limit = _to_float(analysis.get("time_to_limit_hours"))
    if time_to_limit is not None:
        chips.append(f'<span class="chip">{html.escape(f"{time_to_limit:.1f}h 可能触顶")}</span>')
    if analysis.get("warning") is not None:
        chips.append(f'<span class="chip">{html.escape("阈值告警线 " + _format_value(analysis.get("warning"), analysis.get("unit", "")))}</span>')
    return chips


def _primary_suggestion(item: Mapping[str, Any]) -> str:
    if item.get("ai_suggestion"):
        return str(item.get("ai_suggestion"))
    findings = item.get("ai_findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, Mapping) and finding.get("suggestion"):
                return str(finding.get("suggestion"))
    severity = str(item.get("severity") or "unknown")
    if severity in {"critical", "warning"}:
        return "建议优先安排运维排查该实例及上下游依赖，并结合 Grafana 继续观察变化。"
    if severity == "info":
        return "建议保持关注，继续观察后续趋势变化。"
    return "暂无额外动作建议。"


def _strategy_text(item: Mapping[str, Any]) -> str:
    analysis = item.get("analysis") if isinstance(item.get("analysis"), Mapping) else {}
    lines: List[str] = []
    if analysis.get("fallback_current_only"):
        lines.append("本项范围数据查询失败，固定策略已退化为当前值阈值判断。")
    current_value = _format_value(item.get("current_value"), analysis.get("unit", ""))
    lines.append(f"当前值：{current_value}")
    warning = analysis.get("warning")
    critical = analysis.get("critical")
    if warning is not None or critical is not None:
        threshold_text = []
        if warning is not None:
            threshold_text.append(f"预警阈值 { _format_value(warning, analysis.get('unit', '')) }")
        if critical is not None:
            threshold_text.append(f"高危阈值 { _format_value(critical, analysis.get('unit', '')) }")
        lines.append("；".join(threshold_text))
    if analysis.get("fallback_current_only"):
        lines.append(str(item.get("reason") or ""))
        return "\n".join(line for line in lines if line)
    burst = "是" if analysis.get("burst") else "否"
    sustained = "是" if analysis.get("sustained_growth") else "否"
    lines.append(f"是否突增：{burst}")
    lines.append(f"是否持续增长：{sustained}")
    forecast = analysis.get("forecast_24h")
    if forecast is not None:
        lines.append(f"24h 预测值：{_format_value(forecast, analysis.get('unit', ''))}")
    time_to_limit = analysis.get("time_to_limit_hours")
    if time_to_limit is not None:
        try:
            lines.append(f"预计触顶时间：{float(time_to_limit):.1f} 小时")
        except (TypeError, ValueError):
            pass
    lines.append(str(item.get("reason") or ""))
    return "\n".join(line for line in lines if line)


def _render_text_block(text: Any) -> str:
    return _markdownish_to_html(str(text or ""))


def _markdownish_to_html(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return '<p class="muted">无</p>'

    lines = [line.rstrip() for line in stripped.splitlines()]
    parts: List[str] = []
    bullet_buffer: List[str] = []
    number_buffer: List[str] = []
    paragraph_buffer: List[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            content = " ".join(item.strip() for item in paragraph_buffer if item.strip())
            if content:
                parts.append(f"<p>{_inline_markup(content)}</p>")
            paragraph_buffer.clear()

    def flush_bullets() -> None:
        if bullet_buffer:
            parts.append("<ul>" + "".join(f"<li>{_inline_markup(item)}</li>" for item in bullet_buffer) + "</ul>")
            bullet_buffer.clear()

    def flush_numbers() -> None:
        if number_buffer:
            parts.append("<ol>" + "".join(f"<li>{_inline_markup(item)}</li>" for item in number_buffer) + "</ol>")
            number_buffer.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_paragraph()
            flush_bullets()
            flush_numbers()
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", line)
        number = re.match(r"^\d+\.\s+(.+)$", line)
        heading = re.match(r"^#{1,6}\s+(.+)$", line)

        if heading:
            flush_paragraph()
            flush_bullets()
            flush_numbers()
            parts.append(f"<p><strong>{_inline_markup(heading.group(1))}</strong></p>")
            continue
        if bullet:
            flush_paragraph()
            flush_numbers()
            bullet_buffer.append(bullet.group(1))
            continue
        if number:
            flush_paragraph()
            flush_bullets()
            number_buffer.append(number.group(1))
            continue

        flush_bullets()
        flush_numbers()
        paragraph_buffer.append(line)

    flush_paragraph()
    flush_bullets()
    flush_numbers()
    return "".join(parts)


def _inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def _badge(severity: str) -> str:
    label = SEVERITY_LABELS.get(severity, severity or "未知")
    css = html.escape(severity or "unknown")
    return f'<span class="badge {css}">{html.escape(label)}</span>'


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _abs_number(value: Any) -> float:
    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return -1.0
