---
name: inspection-workflow
description: Plan and orchestrate Prometheus inspection workflows for interactive questions and scheduled checks. Use when an agent needs to parse a user request, build an InspectionPlan, choose metric profiles, call Prometheus/Grafana/analysis/report tools in order, enforce safety constraints, and produce table or HTML inspection output.
---

# Inspection Workflow

Use this skill to orchestrate Prometheus inspection. Keep AI decisions outside deterministic computation: tools query, compute, classify, and render; the model plans and explains.

## Interactive Workflow

1. Parse the user request into `target_hint`, `domain`, `time_range`, `instance_hint`, and output preference.
2. Resolve the target with the target resolver tool. If the result is ambiguous, ask one concise clarification.
3. Select metric specs from the metric catalog. Use `metric-domain-knowledge` when the domain is broad or unclear.
4. Generate or adapt PromQL. Use `promql-authoring` when a metric query is missing or the user asks for a custom query.
5. Build an `InspectionPlan`.
6. Validate the plan with tool-side constraints before querying.
7. Query recent current values and historical range samples from Prometheus.
8. Query Grafana alert thresholds when available, then merge thresholds with catalog defaults.
9. Analyze metrics with the analysis tool.
10. Ask the model to explain only from structured evidence returned by the analysis tool.
11. Render table or HTML with the report tool.

## Scheduled Workflow

1. Read approved inspection profiles and target list.
2. Do not generate new PromQL with the model unless the profile explicitly allows it.
3. Query and analyze every configured target/profile pair.
4. Generate HTML and a short structured summary.
5. Use the model only for the final human-readable explanation and suggested follow-up.

## Safety Rules

- Query only resolved and allowed targets.
- Enforce maximum range, maximum series count, and timeout in tools.
- Do not let the model invent thresholds or credentials.
- Treat missing data as `unknown`, not healthy.
- Record threshold source: Grafana alert, catalog default, user input, or none.
- Preserve evidence for every non-healthy result: current value, trend, forecast, threshold, and affected labels.

## Plan Schema

Use this shape when passing work from AI planning to deterministic tools:

```json
{
  "request_id": "optional-id",
  "mode": "interactive",
  "target": {
    "target_id": "prod-prometheus-a"
  },
  "scope": {
    "domain": "redis",
    "instance_hint": "10.0.0.12:9121",
    "job_patterns": ["redis", "redis-exporter"]
  },
  "time": {
    "current_window": "5m",
    "range_hours": 24,
    "step_seconds": 60,
    "forecast_hours": 24
  },
  "items": [
    {
      "id": "redis_memory_usage",
      "domain": "redis",
      "name": "Redis Memory Usage",
      "current_promql": "avg_over_time(redis_memory_used_bytes[5m]) / redis_memory_max_bytes * 100",
      "range_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
      "value_type": "percent",
      "unit": "%",
      "analysis_type": "threshold_trend",
      "direction": "higher_is_bad",
      "warning": 75,
      "critical": 90
    }
  ]
}
```

## Report Sections

Use a stable report shape:

- Overview: target, time range, severity counts.
- High-risk metrics: all `critical`, `warning`, and `watch` items sorted by severity.
- Domain sections: Host, JVM, Redis, RabbitMQ/MQ, Business.
- Unknown or missing-data section.
- Appendix: PromQL, threshold source, and affected labels.
