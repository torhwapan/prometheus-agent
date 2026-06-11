---
name: promql-authoring
description: Create, review, and adapt PromQL for Prometheus inspection tasks, especially when users ask to query host, JVM, Redis, RabbitMQ, MQ, latency, traffic, error-rate, availability, or custom business metrics. Use when an agent needs PromQL examples, metric type guidance, rate/increase rules, histogram quantile patterns, or safe query constraints before calling Prometheus tools.
---

# PromQL Authoring

Use this skill to generate PromQL for inspection plans. Prefer known metric catalog queries when available; generate ad hoc PromQL only for interactive user questions.

## Core Rules

- Convert counters with `rate()` or `increase()` before analysis.
- Use `avg_over_time(metric[5m])` for short-window current state when the raw metric is a gauge.
- Use range queries for trend analysis instead of asking Prometheus for all raw samples at maximum resolution.
- Aggregate only when the inspection question needs aggregation. Preserve `job`, `instance`, `pod`, `namespace`, `queue`, or `mountpoint` labels when the report must identify the risky object.
- Use `histogram_quantile()` for classic Prometheus histograms.
- Prefer percentages for utilization and success/error ratios when thresholds are percent-based.
- Add label filters from the resolved target scope. Do not invent production target URLs or credentials.
- Keep time windows bounded. Default to current window `5m`, trend window `24h`, and range query step `60s` or larger unless the platform provides stricter defaults.

## Query Pattern Selection

- Host resources: read [references/host.md](references/host.md).
- JVM metrics: read [references/jvm.md](references/jvm.md).
- Redis metrics: read [references/redis.md](references/redis.md).
- RabbitMQ and queue metrics: read [references/rabbitmq.md](references/rabbitmq.md).
- Generic business metrics: read [references/business.md](references/business.md).

## Output Contract

When producing a query for an inspection plan, return these fields:

```json
{
  "id": "metric_id",
  "name": "Human readable name",
  "current_promql": "PromQL for recent state",
  "range_promql": "PromQL for historical trend",
  "unit": "%",
  "value_type": "percent",
  "analysis_type": "threshold_trend",
  "direction": "higher_is_bad",
  "labels_to_keep": ["job", "instance"]
}
```

Use `current_promql` for recent 5-minute state and `range_promql` for trend sampling.
