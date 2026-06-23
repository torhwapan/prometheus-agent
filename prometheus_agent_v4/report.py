"""Inspection-style HTML report rendering for Prometheus agent v4."""

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
    top_risks = sorted(risky_items, key=_item_sort_key, reverse=True)[:10]
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
    inspection_id = str(meta.get("inspection_id") or plan.get("inspection_id") or "").strip()
    toc_items = _build_toc_items(grouped)
    detail_sections = [_render_job_section(job, instances) for job, instances in grouped]
    risk_rows = [_render_risk_row(item) for item in top_risks]
    summary_source = ai_correlation.get("summary") if isinstance(ai_correlation, Mapping) else executive_summary
    focus_list = _render_focus_list(top_risks)
    inspection_note = _build_inspection_note(plan, counts, total)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prometheus 巡检报告</title>
  <style>
    :root {{
      --page-bg: #f3f6f8;
      --paper: #ffffff;
      --paper-subtle: #f8fafb;
      --paper-strong: #f0f4f6;
      --text: #16212b;
      --muted: #61717f;
      --line: #d9e1e7;
      --line-strong: #c7d2dc;
      --navy: #1f3c59;
      --navy-soft: #2c547d;
      --accent: #2a6f97;
      --critical: #b42318;
      --critical-bg: #fde8e6;
      --warning: #b54708;
      --warning-bg: #fff1dd;
      --info: #175cd3;
      --info-bg: #e8f1ff;
      --ok: #027a48;
      --ok-bg: #e7f8ef;
      --unknown: #667085;
      --unknown-bg: #eff2f5;
      --shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
      background: linear-gradient(180deg, #eef3f6 0%, var(--page-bg) 100%);
    }}
    a {{
      color: inherit;
      text-decoration: none;
    }}
    .page {{
      max-width: 1380px;
      margin: 0 auto;
      padding: 24px 20px 48px;
    }}
    .report-shell {{
      position: relative;
    }}
    .toc {{
      position: fixed;
      left: calc(max(12px, calc((100vw - 1380px) / 2 + 20px)) - 54px);
      top: 32px;
      z-index: 30;
    }}
    .toc summary {{
      list-style: none;
    }}
    .toc summary::-webkit-details-marker {{
      display: none;
    }}
    .toc-button {{
      width: 42px;
      height: 42px;
      border-radius: 999px;
      border: 1px solid rgba(217, 225, 231, 0.95);
      background: rgba(255, 255, 255, 0.97);
      box-shadow: 0 10px 22px rgba(22, 33, 43, 0.12);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: #284766;
      transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
    }}
    .toc-button:hover {{
      transform: translateY(-1px);
      box-shadow: 0 14px 28px rgba(22, 33, 43, 0.16);
      background: #fff;
    }}
    .toc-icon {{
      position: relative;
      width: 14px;
      height: 12px;
    }}
    .toc-icon::before,
    .toc-icon::after,
    .toc-icon span {{
      content: "";
      position: absolute;
      left: 0;
      width: 14px;
      height: 2px;
      border-radius: 999px;
      background: currentColor;
    }}
    .toc-icon::before {{
      top: 0;
    }}
    .toc-icon span {{
      top: 5px;
    }}
    .toc-icon::after {{
      top: 10px;
    }}
    .toc-panel {{
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      width: 224px;
      min-width: 224px;
      padding: 10px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.98);
      backdrop-filter: blur(10px);
      box-shadow: var(--shadow);
      opacity: 0;
      pointer-events: none;
      transform: translateY(-4px);
      transition: opacity 0.18s ease, transform 0.18s ease;
    }}
    .toc[open] .toc-panel {{
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0);
    }}
    .toc-link {{
      display: flex;
      align-items: center;
      min-height: 34px;
      padding: 7px 10px;
      border-radius: 10px;
      color: #203547;
      font-size: 12px;
      font-weight: 600;
      line-height: 1.5;
    }}
    .toc-link:hover {{
      background: #eef4f8;
    }}
    .toc-link + .toc-link {{
      margin-top: 2px;
    }}
    .toc-link-child {{
      position: relative;
      padding-left: 26px;
      font-size: 12px;
      font-weight: 500;
      color: var(--muted);
    }}
    .toc-link-child::before {{
      content: "";
      position: absolute;
      left: 12px;
      top: 15px;
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: #c4d0da;
    }}
    .content {{
      min-width: 0;
    }}
    .hero {{
      background: linear-gradient(180deg, #fcfdfd 0%, #f6f8f9 100%);
      color: var(--text);
      border: 1px solid var(--line);
      border-top: 4px solid #4b5563;
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 26px 28px 24px;
      position: relative;
      overflow: hidden;
    }}
    .hero::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 6px;
      background: linear-gradient(180deg, #4b5563 0%, #7a846f 100%);
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -90px;
      top: -90px;
      width: 260px;
      height: 260px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(75, 85, 99, 0.08) 0%, rgba(75, 85, 99, 0.03) 55%, transparent 75%);
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }}
    .hero-kicker {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: #eef1f4;
      color: #52606d;
      font-size: 12px;
      letter-spacing: 0.04em;
    }}
    .hero h1 {{
      margin: 12px 0 10px;
      font-size: 32px;
      line-height: 1.18;
      color: #15222d;
    }}
    .hero p {{
      margin: 0;
      max-width: 940px;
      color: #4f6170;
      line-height: 1.72;
      font-size: 14px;
    }}
    .report-stamp {{
      text-align: right;
      min-width: 200px;
      position: relative;
      z-index: 1;
    }}
    .report-stamp .stamp-label {{
      font-size: 12px;
      color: #6d7984;
    }}
    .report-stamp .stamp-value {{
      margin-top: 6px;
      font-size: 14px;
      font-weight: 700;
      color: #15222d;
      word-break: break-word;
    }}
    .hero-meta {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
      position: relative;
      z-index: 1;
    }}
    .hero-meta-card {{
      padding: 12px 14px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid var(--line);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
    }}
    .hero-meta-card .label {{
      display: block;
      font-size: 12px;
      color: #6d7984;
      margin-bottom: 6px;
    }}
    .hero-meta-card .value {{
      font-size: 14px;
      color: #15222d;
      line-height: 1.55;
      word-break: break-word;
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .stat-card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px 18px 16px;
      box-shadow: var(--shadow);
    }}
    .stat-card .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }}
    .stat-card .value {{
      font-size: 30px;
      font-weight: 700;
      line-height: 1;
      color: #1c2c3a;
    }}
    .stat-card .sub {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .section {{
      margin-top: 18px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 16px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .section-anchor {{
      scroll-margin-top: 18px;
    }}
    .section-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 20px 0;
    }}
    .section-title-wrap h2 {{
      margin: 0;
      font-size: 21px;
      line-height: 1.25;
      color: #1e3142;
    }}
    .section-title-wrap p {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.7;
    }}
    .section-body {{
      padding: 18px 20px 20px;
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
    .overview-grid {{
      display: grid;
      grid-template-columns: 1.45fr 1fr;
      gap: 16px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--paper-subtle);
      padding: 16px;
    }}
    .panel h3 {{
      margin: 0 0 12px;
      font-size: 15px;
      color: #24384b;
    }}
    .panel p,
    .panel li {{
      line-height: 1.72;
      color: var(--text);
      font-size: 14px;
    }}
    .panel ul,
    .panel ol {{
      margin: 0;
      padding-left: 18px;
    }}
    .count-list {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .count-item {{
      padding: 12px 12px 10px;
      border-radius: 12px;
      background: #fff;
      border: 1px solid var(--line);
    }}
    .count-item strong {{
      display: block;
      font-size: 22px;
      line-height: 1;
      margin-bottom: 6px;
    }}
    .note-list {{
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }}
    .note-item {{
      display: grid;
      grid-template-columns: 96px minmax(0, 1fr);
      gap: 10px;
      align-items: start;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
    }}
    .note-item .key {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .note-item .value {{
      color: var(--text);
      font-size: 13px;
      line-height: 1.7;
      word-break: break-word;
    }}
    .focus-list {{
      display: grid;
      gap: 10px;
    }}
    .focus-item {{
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 12px;
      align-items: start;
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: var(--paper-subtle);
    }}
    .focus-main {{
      min-width: 0;
    }}
    .focus-title {{
      font-weight: 700;
      line-height: 1.5;
      margin-bottom: 4px;
    }}
    .focus-meta {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
      margin-bottom: 6px;
    }}
    .focus-reason {{
      color: var(--text);
      font-size: 13px;
      line-height: 1.7;
    }}
    .risk-table,
    .detail-table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: hidden;
      background: #fff;
    }}
    .risk-table thead th,
    .detail-table thead th {{
      background: var(--paper-strong);
      color: #38536a;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .risk-table th,
    .risk-table td,
    .detail-table th,
    .detail-table td {{
      padding: 12px 12px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      line-height: 1.65;
    }}
    .risk-table tr:last-child td,
    .detail-table tr:last-child td {{
      border-bottom: none;
    }}
    .metric-name {{
      font-weight: 700;
      color: #203345;
      margin-bottom: 4px;
      line-height: 1.45;
    }}
    .metric-id {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
      word-break: break-all;
    }}
    .muted {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.65;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }}
    .chip {{
      display: inline-flex;
      padding: 4px 8px;
      border-radius: 999px;
      background: #edf3f7;
      color: #39566e;
      font-size: 12px;
      line-height: 1;
    }}
    .trend-cell {{
      min-width: 180px;
    }}
    .text-block p {{
      margin: 0 0 8px;
      line-height: 1.72;
    }}
    .text-block ul,
    .text-block ol {{
      margin: 0 0 8px;
      padding-left: 18px;
      line-height: 1.72;
    }}
    .text-block code {{
      padding: 1px 6px;
      border-radius: 8px;
      background: rgba(39, 71, 103, 0.08);
      font-family: Consolas, monospace;
      font-size: 0.92em;
    }}
    .callout {{
      padding: 14px 16px;
      border-radius: 12px;
      border: 1px solid #d8e5ef;
      background: linear-gradient(180deg, #f7fbff 0%, #f3f8fc 100%);
    }}
    .correlation-list {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 14px;
    }}
    .correlation-card {{
      padding: 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: var(--paper-subtle);
    }}
    .correlation-card h3 {{
      margin: 10px 0 8px;
      font-size: 16px;
      line-height: 1.45;
    }}
    .correlation-card p {{
      margin: 0 0 8px;
      line-height: 1.72;
      font-size: 13px;
    }}
    .job-section + .job-section {{
      margin-top: 16px;
    }}
    .job-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      padding: 16px 18px;
      background: #f7fafc;
      border: 1px solid var(--line);
      border-radius: 14px;
    }}
    .job-head h3 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.35;
      color: #21384b;
    }}
    .job-head p {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.68;
    }}
    .instance-section {{
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--paper-subtle);
      overflow: hidden;
    }}
    .instance-section summary {{
      list-style: none;
      cursor: pointer;
      padding: 16px 18px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      background: #fff;
    }}
    .instance-section summary::-webkit-details-marker {{
      display: none;
    }}
    .instance-title {{
      font-weight: 700;
      margin-bottom: 6px;
      line-height: 1.45;
    }}
    .instance-meta {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.65;
    }}
    .instance-body {{
      padding: 0 16px 16px;
    }}
    .progress {{
      width: 126px;
      height: 8px;
      border-radius: 999px;
      background: #e7edf2;
      overflow: hidden;
      margin-top: 8px;
    }}
    .progress > span {{
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #2f6fed, #2d8b76);
    }}
    .empty {{
      padding: 18px;
      border-radius: 12px;
      border: 1px dashed var(--line-strong);
      background: #fbfcfd;
      color: var(--muted);
      line-height: 1.72;
      font-size: 13px;
    }}
    @media (max-width: 1180px) {{
      .toc {{
        left: 12px;
        top: 20px;
      }}
      .toc-panel {{
        top: calc(100% + 8px);
        left: auto;
        right: 0;
        transform: translateY(-4px);
      }}
      .hero-meta,
      .stat-grid,
      .overview-grid,
      .correlation-list {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 860px) {{
      .page {{
        padding: 14px 12px 30px;
      }}
      .toc {{
        top: 12px;
      }}
      .toc-panel {{
        width: min(224px, calc(100vw - 24px));
        min-width: 0;
      }}
      .hero {{
        padding: 22px 18px 18px;
      }}
      .hero-top {{
        display: block;
      }}
      .report-stamp {{
        margin-top: 14px;
        text-align: left;
        min-width: 0;
      }}
      .hero h1 {{
        font-size: 26px;
      }}
      .hero-meta,
      .stat-grid,
      .overview-grid,
      .correlation-list,
      .count-list {{
        grid-template-columns: 1fr;
      }}
      .risk-table,
      .detail-table {{
        display: block;
        overflow-x: auto;
      }}
      .section-head,
      .job-head,
      .instance-section summary {{
        display: block;
      }}
      .section-body {{
        padding: 16px;
      }}
      .note-item {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="report-shell">
      <details class="toc">
        <summary>
          <div class="toc-button" aria-hidden="true"><div class="toc-icon"><span></span></div></div>
        </summary>
        <div class="toc-panel">
          {''.join(toc_items)}
        </div>
      </details>

      <main class="content">
        <section class="hero">
          <div class="hero-top">
            <div>
              <div class="hero-kicker">Prometheus Inspection Report</div>
              <h1>Prometheus 巡检报告</h1>
              <p>{html.escape(executive_summary)}</p>
            </div>
            <div class="report-stamp">
              <div class="stamp-label">报告编号</div>
              <div class="stamp-value">{html.escape(inspection_id or "未指定")}</div>
              <div class="stamp-label" style="margin-top:12px;">生成时间</div>
              <div class="stamp-value">{html.escape(report_time)}</div>
            </div>
          </div>
          <div class="hero-meta">
            <div class="hero-meta-card">
              <span class="label">Prometheus 地址</span>
              <div class="value">{html.escape(_display_prometheus(plan.get("prometheus_url")))}</div>
            </div>
            <div class="hero-meta-card">
              <span class="label">巡检范围</span>
              <div class="value">{html.escape(_display_scope(plan.get("job"), plan.get("instance")))}</div>
            </div>
            <div class="hero-meta-card">
              <span class="label">时间窗口</span>
              <div class="value">{html.escape(_display_time_window(plan))}</div>
            </div>
            <div class="hero-meta-card">
              <span class="label">数据粒度</span>
              <div class="value">{html.escape(_display_sampling(plan))}</div>
            </div>
          </div>
        </section>

        <section class="stat-grid">
          <div class="stat-card">
            <div class="label">总体风险等级</div>
            <div class="value">{html.escape(SEVERITY_LABELS.get(str(analysis.get("severity") or "unknown"), "未知"))}</div>
            <div class="sub">{_badge(str(analysis.get("severity") or "unknown"))}</div>
          </div>
          <div class="stat-card">
            <div class="label">重点关注指标</div>
            <div class="value">{len(risky_items)}</div>
            <div class="sub">总计巡检 {total} 项指标</div>
          </div>
          <div class="stat-card">
            <div class="label">巡检对象</div>
            <div class="value">{job_count}</div>
            <div class="sub">Job 数量 / 实例数 {instance_count}</div>
          </div>
          <div class="stat-card">
            <div class="label">高优先风险</div>
            <div class="value">{counts["critical"] + counts["warning"]}</div>
            <div class="sub">高危 {counts["critical"]} / 预警 {counts["warning"]}</div>
          </div>
        </section>

        <section id="section-summary" class="section section-anchor">
          <div class="section-head">
            <div class="section-title-wrap">
              <h2>一、执行摘要</h2>
              <p>这一部分用于汇报整体风险、优先关注对象和本次巡检说明。</p>
            </div>
          </div>
          <div class="section-body">
            <div class="overview-grid">
              <div class="panel">
                <h3>总体结论</h3>
                <div class="text-block">{_render_text_block(summary_source)}</div>
              </div>
              <div class="panel">
                <h3>风险统计</h3>
                <div class="count-list">
                  {_render_count_item("高危", counts["critical"], "critical")}
                  {_render_count_item("预警", counts["warning"], "warning")}
                  {_render_count_item("关注", counts["info"], "info")}
                  {_render_count_item("正常", counts["ok"], "ok")}
                </div>
                <div class="note-list">
                  {_render_note_item("分析方式", "固定策略分析 + AI 解释分析")}
                  {_render_note_item("固定策略", "突增检测、持续增长检测、24h 预测、预计触顶时间")}
                  {_render_note_item("风险依据", "风险统计基于 Python 固定策略计算，不以 AI 主观判断为准")}
                </div>
              </div>
            </div>
            <div class="panel" style="margin-top:16px;">
              <h3>巡检说明</h3>
              <div class="note-list">
                {_render_note_item("巡检对象", _display_scope(plan.get("job"), plan.get("instance")))}
                {_render_note_item("时间范围", _display_time_window(plan))}
                {_render_note_item("采样说明", _display_sampling(plan))}
                {_render_note_item("补充说明", inspection_note)}
              </div>
            </div>
          </div>
        </section>

        <section id="section-focus" class="section section-anchor">
          <div class="section-head">
            <div class="section-title-wrap">
              <h2>二、重点关注项</h2>
              <p>先给出领导视角下最需要关注的对象，再进入完整指标表格。</p>
            </div>
          </div>
          <div class="section-body">
            {focus_list}
          </div>
        </section>

        <section id="section-risks" class="section section-anchor">
          <div class="section-head">
            <div class="section-title-wrap">
              <h2>三、重点风险指标</h2>
              <p>仅展示非正常指标，适合快速定位异常实例、异常指标和建议动作。</p>
            </div>
          </div>
          <div class="section-body">
            {('<table class="risk-table"><thead><tr><th>等级</th><th>指标</th><th>对象</th><th>当前值</th><th>固定策略分析</th><th>AI 分析</th><th>建议动作</th></tr></thead><tbody>' + ''.join(risk_rows) + '</tbody></table>') if risk_rows else '<div class="empty">本次巡检没有发现需要重点汇报的异常指标。</div>'}
          </div>
        </section>

        <section id="section-correlation" class="section section-anchor">
          <div class="section-head">
            <div class="section-title-wrap">
              <h2>四、关联分析</h2>
              <p>从多指标、多组件角度补充解释，帮助判断是否属于同一问题链路。</p>
            </div>
          </div>
          <div class="section-body">
            <div class="callout text-block">{_render_text_block(ai_correlation.get("summary") if isinstance(ai_correlation, Mapping) else "暂无 AI 关联分析结论。")}</div>
            {('<div class="correlation-list">' + ''.join(correlation_cards) + '</div>') if correlation_cards else '<div class="empty" style="margin-top:14px;">暂无跨指标关联风险结论。</div>'}
          </div>
        </section>

        <section id="section-details" class="section section-anchor">
          <div class="section-head">
            <div class="section-title-wrap">
              <h2>五、分组明细</h2>
              <p>按 job 和 instance 逐层展开，兼顾管理汇报和技术排查。</p>
            </div>
          </div>
          <div class="section-body">
            {''.join(detail_sections) if detail_sections else '<div class="empty">没有可展示的指标明细。</div>'}
          </div>
        </section>
      </main>
    </div>
  </div>
  <script>
    (function () {{
      var toc = document.querySelector('details.toc');
      if (!toc) return;
      toc.querySelectorAll('.toc-link').forEach(function (link) {{
        link.addEventListener('click', function () {{
          toc.removeAttribute('open');
        }});
      }});
    }})();
  </script>
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
    return f"本次巡检共检查 {total} 项指标，其中 {risky_count} 项需要关注，整体风险等级为{severity}。建议优先查看下方重点关注项、重点风险指标和关联分析。"


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


def _build_toc_items(grouped: Sequence[Tuple[str, List[Tuple[str, List[Mapping[str, Any]]]]]]) -> List[str]:
    items: List[str] = [
        "<a class='toc-link' href='#section-summary'>一、执行摘要</a>",
        "<a class='toc-link' href='#section-focus'>二、重点关注项</a>",
        "<a class='toc-link' href='#section-risks'>三、重点风险指标</a>",
        "<a class='toc-link' href='#section-correlation'>四、关联分析</a>",
        "<a class='toc-link' href='#section-details'>五、分组明细</a>",
    ]
    for job, _instances in grouped:
        items.append(
            f"<a class='toc-link toc-link-child' href='#{html.escape(_job_anchor(job))}'>{html.escape(job)}</a>"
        )
    return items


def _render_job_section(job: str, instances: Sequence[Tuple[str, List[Mapping[str, Any]]]]) -> str:
    risky_count = sum(1 for _, values in instances for item in values if str(item.get("severity") or "unknown") != "ok")
    total = sum(len(values) for _, values in instances)
    top_severity = max((_severity_rank(str(item.get("severity") or "unknown")) for _, values in instances for item in values), default=0)
    blocks = [_render_instance_section(instance, values) for instance, values in instances]
    return (
        f'<div id="{html.escape(_job_anchor(job))}" class="job-section section-anchor">'
        '<div class="job-head">'
        f'<div><h3>{html.escape(job)}</h3><p>{html.escape(f"共 {len(instances)} 个实例，巡检 {total} 项指标，需关注 {risky_count} 项。")}</p></div>'
        f'<div>{_badge(_severity_from_rank(top_severity))}</div>'
        "</div>"
        f'{"".join(blocks)}'
        "</div>"
    )


def _render_instance_section(instance: str, items: Sequence[Mapping[str, Any]]) -> str:
    risky = [item for item in items if str(item.get("severity") or "unknown") != "ok"]
    top_severity = max((_severity_rank(str(item.get("severity") or "unknown")) for item in items), default=0)
    summary = f"{len(items)} 项指标，需关注 {len(risky)} 项"
    rows = "".join(_render_detail_row(item) for item in items)
    open_attr = " open" if risky or top_severity >= _severity_rank("warning") else ""
    badge = _badge(_severity_from_rank(top_severity))
    return (
        f'<details class="instance-section"{open_attr}>'
        "<summary>"
        f"<div><div class='instance-title'>{html.escape(instance)}</div><div class='instance-meta'>{html.escape(summary)}</div></div>"
        f"<div>{badge}</div>"
        "</summary>"
        '<div class="instance-body">'
        '<table class="detail-table">'
        "<thead><tr><th>等级</th><th>指标</th><th>当前值</th><th>趋势摘要</th><th>固定策略分析</th><th>AI 分析</th></tr></thead>"
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
        f"<td class='text-block'>{_render_text_block(item.get('ai_comment') or '暂无 AI 补充分析。')}</td>"
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
        f"<td class='trend-cell'>{trend_html}<div class='chips'>{''.join(_trend_chips(analysis))}</div></td>"
        f"<td class='text-block'>{_render_text_block(_strategy_text(item))}</td>"
        f"<td class='text-block'>{_render_text_block(item.get('ai_comment') or item.get('ai_suggestion') or '无')}</td>"
        "</tr>"
    )


def _render_focus_list(items: Sequence[Mapping[str, Any]]) -> str:
    if not items:
        return '<div class="empty">本次巡检未发现需要单独提请关注的风险项。</div>'
    rows = []
    for item in items[:6]:
        reason = _compact_reason(item)
        rows.append(
            '<div class="focus-item">'
            f"{_badge(str(item.get('severity') or 'unknown'))}"
            '<div class="focus-main">'
            f"<div class='focus-title'>{html.escape(str(item.get('metric_name') or item.get('metric_id') or ''))}</div>"
            f"<div class='focus-meta'>{html.escape(str(item.get('job') or ''))} / {html.escape(str(item.get('instance') or ''))} / 当前值 {html.escape(_format_value(item.get('current_value'), _analysis_unit(item)))}</div>"
            f"<div class='focus-reason'>{html.escape(reason)}</div>"
            "</div>"
            "</div>"
        )
    return "<div class='focus-list'>" + "".join(rows) + "</div>"


def _compact_reason(item: Mapping[str, Any]) -> str:
    strategy = str(_strategy_text(item) or "").strip().replace("\n", "；")
    ai_comment = str(item.get("ai_comment") or "").strip()
    if ai_comment:
        return f"{strategy}。AI 分析：{ai_comment[:120]}" if strategy else ai_comment[:120]
    return strategy or "当前需要进一步关注该指标变化。"


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


def _render_note_item(label: str, value: str) -> str:
    return (
        '<div class="note-item">'
        f"<div class='key'>{html.escape(label)}</div>"
        f"<div class='value'>{html.escape(value)}</div>"
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


def _display_sampling(plan: Mapping[str, Any]) -> str:
    step = plan.get("step_seconds")
    current_window = str(plan.get("current_window") or "").strip()
    step_text = f"{step} 秒/点" if step else "默认采样步长"
    if current_window:
        return f"当前值窗口 {current_window}；范围采样 {step_text}"
    return f"范围采样 {step_text}"


def _build_inspection_note(plan: Mapping[str, Any], counts: Mapping[str, int], total: int) -> str:
    if total <= 0:
        return "本次未形成可用于展示的指标结果。"
    high_priority = int(counts.get("critical", 0)) + int(counts.get("warning", 0))
    if high_priority > 0:
        return f"本次巡检存在 {high_priority} 项高优先级风险，建议优先结合 Grafana 与实例侧日志排查。"
    if int(counts.get("info", 0)) > 0:
        return "本次巡检以趋势类关注项为主，建议持续观察后续 24 小时变化。"
    return "本次巡检整体平稳，未发现明显高风险指标。"


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


def _analysis_unit(item: Mapping[str, Any]) -> str:
    analysis = item.get("analysis") if isinstance(item.get("analysis"), Mapping) else {}
    return str(analysis.get("unit") or "")


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
        return "范围趋势获取失败，本项没有可用的趋势分析结果"
    parts: List[str] = []
    forecast = analysis.get("forecast_24h")
    if forecast is not None:
        parts.append(f"24h 预测 {_format_value(forecast, analysis.get('unit', ''))}")
    slope = analysis.get("slope_per_hour")
    if slope is not None:
        parts.append(f"每小时变化 {_format_value(slope, analysis.get('unit', ''))}")
    return "；".join(parts) if parts else "当前未形成有效趋势结论"


def _trend_chips(analysis: Mapping[str, Any]) -> List[str]:
    chips = []
    if analysis.get("fallback_current_only"):
        chips.append('<span class="chip">仅当前值判断</span>')
        return chips
    if analysis.get("burst"):
        chips.append('<span class="chip">存在突增</span>')
    if analysis.get("sustained_growth"):
        chips.append('<span class="chip">持续增长</span>')
    time_to_limit = _to_float(analysis.get("time_to_limit_hours"))
    if time_to_limit is not None:
        chips.append(f'<span class="chip">{html.escape(f"{time_to_limit:.1f}h 可能触顶")}</span>')
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
        lines.append("范围趋势查询失败，本项未执行突增和持续增长分析。")
        return "\n".join(line for line in lines if line)
    burst_flag = analysis.get("burst")
    sustained_flag = analysis.get("sustained_growth")
    if burst_flag is True:
        lines.append("突增检测：发现突增")
    elif burst_flag is False:
        lines.append("突增检测：未发现突增")
    if sustained_flag is True:
        lines.append("持续增长检测：发现持续增长")
    elif sustained_flag is False:
        lines.append("持续增长检测：未发现持续增长")
    forecast = analysis.get("forecast_24h")
    if forecast is not None and sustained_flag:
        lines.append(f"24h 预测值：{_format_value(forecast, analysis.get('unit', ''))}")
    time_to_limit = analysis.get("time_to_limit_hours")
    if time_to_limit is not None and sustained_flag:
        try:
            lines.append(f"预计触顶时间：{float(time_to_limit):.1f} 小时")
        except (TypeError, ValueError):
            pass
    if not lines:
        lines.append("固定策略未发现明显趋势异常。")
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


def _severity_from_rank(rank: int) -> str:
    for severity, value in SEVERITY_ORDER.items():
        if value == rank:
            return severity
    return "unknown"


def _job_anchor(job: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(job or "").strip()).strip("-").lower()
    return f"job-{slug or 'unknown'}"


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
