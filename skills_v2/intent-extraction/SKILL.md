---
name: prometheus-v2-intent-extraction
description: Extract Prometheus inspection intent from Chinese or English chat requests. Use when the platform needs to parse prometheus_url, job name, instance name, time range, and report scope before calling v2 Python HTTP tools. Job and instance are optional and must default to all when missing.
---

# Prometheus V2 Intent Extraction

Extract only the fields needed to call the Python HTTP service. Do not invent missing job or instance values.

## Output JSON

Return this shape:

```json
{
  "prometheus_url": "http://127.0.0.1:9090",
  "job": null,
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m",
  "need_ai_series_analysis": true,
  "need_ai_correlation": true
}
```

## Extraction Rules

- `prometheus_url` is required. If missing, ask the user for it.
- `job` is optional. If the user says Redis, JVM, RabbitMQ, or node-exporter, map it to a configured job family when possible.
- `instance` is optional. Preserve exact host:port strings such as `10.0.0.1:9100`.
- Default `range_hours` to 24 unless the user asks for another window.
- Default `step_seconds` to 60 unless the user asks for higher resolution.
- Default `current_window` to `5m`.
- Do not validate connectivity. The Python service does that.

## Examples

User: `请帮我看下 http://127.0.0.1:9090 上 redis 有没有异常`

```json
{
  "prometheus_url": "http://127.0.0.1:9090",
  "job": "redis",
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m",
  "need_ai_series_analysis": true,
  "need_ai_correlation": true
}
```

User: `查一下 10.1.2.3:9100 这台机器最近 6 小时`

```json
{
  "prometheus_url": null,
  "job": "node",
  "instance": "10.1.2.3:9100",
  "range_hours": 6,
  "step_seconds": 60,
  "current_window": "5m",
  "need_ai_series_analysis": true,
  "need_ai_correlation": true
}
```
