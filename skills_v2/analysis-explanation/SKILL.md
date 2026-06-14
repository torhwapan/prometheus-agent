---
name: prometheus-v2-analysis-explanation
description: Generate short AI explanations for Prometheus metric samples and cross-metric correlation based strictly on structured data from v2 Python tools. Use when producing <=100 character or <=100 word metric comments, root-cause hypotheses, and operator suggestions after deterministic analysis has already run.
---

# Prometheus V2 Analysis Explanation

Use only evidence from Python tool output. Do not invent values, thresholds, or root causes.

## Per-Metric Comment

For step 5, generate a short comment under 100 Chinese characters or under 100 English words.

Input evidence usually includes:

- job
- instance
- metric id and name
- severity
- current value
- min, max, average, p95
- recent change ratio
- slope per hour
- burst flag
- sustained growth flag
- time to limit

Comment style:

```text
过去24小时持续上升，当前未越线，但按趋势可能在12小时内接近阈值。
```

If evidence is insufficient:

```text
样本不足，无法判断趋势，建议检查采集状态。
```

## Correlation Analysis

For step 6, group risky metrics by `job` and `instance`.

Prioritize these relationships:

- Host CPU/memory high plus JVM GC high: possible application pressure or memory leak.
- Redis memory high plus evictions/rejected connections: possible cache capacity pressure.
- RabbitMQ ready/unacked growth plus low consumers: possible consumer lag or consumer outage.
- Traffic burst plus latency/error increase: possible load-induced degradation.

Keep conclusions cautious. Use phrases such as `可能`, `建议优先检查`, and `需要结合日志确认`.

## Output Contract

Return structured text:

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
