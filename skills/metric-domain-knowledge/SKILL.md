---
name: metric-domain-knowledge
description: Select and explain core inspection metrics for Prometheus-monitored domains including host, JVM, Redis, RabbitMQ, MQ, latency, availability, error-rate, and custom business metrics. Use when deciding which metrics are common/core, which are domain-specific, what risks they indicate, and which analysis type should be applied.
---

# Metric Domain Knowledge

Use this skill to select inspection metrics and explain their operational meaning. Keep the metric set small enough for a reliable inspection report; prefer core risk indicators over exhaustive metric scraping.

## Selection Rules

- Start with a domain profile: `host`, `jvm`, `redis`, `rabbitmq`, `business`, or a combination.
- Prefer metrics with clear operational meaning and actionable owners.
- Preserve labels that identify the affected object, such as `instance`, `pod`, `namespace`, `queue`, `vhost`, `mountpoint`, and `job`.
- Do not classify every Prometheus metric as a core metric. Many exporter metrics are diagnostic details, not first-level inspection items.
- Use configured thresholds when available. If no threshold exists, use trend or baseline analysis and mark uncertainty in the output.

## Domain References

- Host: read [references/host.md](references/host.md).
- JVM: read [references/jvm.md](references/jvm.md).
- Redis: read [references/redis.md](references/redis.md).
- RabbitMQ and MQ: read [references/rabbitmq.md](references/rabbitmq.md).
- Business metrics: read [references/business.md](references/business.md).

## Output Contract

When selecting metrics for an inspection plan, return metric specs with:

```json
{
  "id": "redis_memory_usage",
  "domain": "redis",
  "name": "Redis Memory Usage",
  "risk": "Redis may approach configured maxmemory and start evicting keys.",
  "analysis_type": "threshold_trend",
  "value_type": "percent",
  "direction": "higher_is_bad",
  "recommended_labels": ["job", "instance"],
  "threshold_policy": "grafana_or_catalog"
}
```
