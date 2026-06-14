---
name: prometheus-v2-analysis-explanation
description: Generate AI supplemental analysis for Prometheus metric range samples and cross-metric correlation based strictly on structured data from v2 Python tools. Use when analyzing sampled time-series data from /v2/build-ai-series-inputs, producing short per-metric findings, root-cause hypotheses, operator suggestions, and correlation JSON after deterministic Python analysis has already run.
---

# Prometheus V2 Analysis Explanation

Use only evidence from Python tool output. Do not invent values, thresholds, instances, labels, or root causes.

## Per-Metric Range Sample Analysis

For Step 5, analyze the compact range sample payload produced by `/v2/build-ai-series-inputs`.

The AI's job is supplemental:

- Observe historical samples for patterns not covered by fixed rules.
- Keep `python_severity` unchanged.
- Return short structured findings for the report.
- Do not replace Python deterministic analysis.

Input evidence usually includes:

- `job`
- `instance`
- `metric_id`
- `metric_name`
- `series_labels`
- `python_severity`
- `python_reason`
- `python_analysis`
- `sample_policy`
- `range_points`

Look for:

- periodic fluctuation
- long plateau followed by uplift
- frequent oscillation
- repeated near-threshold recovery
- sampling gaps
- outliers
- current value clearly different from most historical samples

Return JSON:

```json
{
  "job": "redis",
  "instance": "10.0.0.12:9121",
  "metric_id": "redis_memory_usage",
  "summary": "内存使用率持续处于高位，未看到明显回落。",
  "extra_risks": [
    "高位平台期持续时间较长"
  ],
  "suggestion": "建议检查 key 增长、过期策略和 maxmemory 配置。"
}
```

If there is no extra finding:

```json
{
  "job": "redis",
  "instance": "10.0.0.12:9121",
  "metric_id": "redis_memory_usage",
  "summary": "未发现固定规则之外的明显额外异常。",
  "extra_risks": [],
  "suggestion": "继续按当前巡检等级关注即可。"
}
```

## Correlation Analysis

For Step 6, group risky metrics by `job` and `instance`.

Prioritize these relationships:

- Host CPU/memory high plus JVM GC high: possible application pressure or memory leak.
- Redis memory high plus evictions/rejected connections: possible cache capacity pressure.
- RabbitMQ ready/unacked growth plus low consumers: possible consumer lag or consumer outage.
- Traffic burst plus latency/error increase: possible load-induced degradation.

Keep conclusions cautious. Use phrases such as `可能`, `建议优先检查`, and `需要结合日志确认`.

Return JSON:

```json
{
  "summary": "整体风险摘要",
  "correlations": [
    {
      "level": "warning",
      "job": "redis",
      "instance": "10.0.0.1:9121",
      "reason": "多个内存相关指标同时恶化",
      "suggestion": "检查 maxmemory、key 增长和淘汰策略"
    }
  ]
}
```
