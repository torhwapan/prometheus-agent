# Business Metric PromQL Patterns

Business metrics need explicit metric ownership and semantic thresholds. Do not invent thresholds.

## Error Rate

```promql
sum by(job, instance) (rate(http_requests_total{status=~"5.."}[5m]))
/
sum by(job, instance) (rate(http_requests_total[5m]))
* 100
```

Use `error_rate`, `higher_is_bad`, unit `%`.

## Success Rate

```promql
sum by(job, instance) (rate(http_requests_total{status!~"5.."}[5m]))
/
sum by(job, instance) (rate(http_requests_total[5m]))
* 100
```

Use `availability`, `lower_is_bad`, unit `%`.

## Latency P95

Classic histogram:

```promql
histogram_quantile(0.95, sum by(le, job, instance) (rate(http_request_duration_seconds_bucket[5m])))
```

Use `latency`, `higher_is_bad`, unit `s`.

## Traffic

```promql
sum by(job, instance) (rate(http_requests_total[5m]))
```

Use `seasonal_baseline`, `burst_detection`, or `rate_change`; raw traffic is not usually bad by itself.

## Orders or Payments

Use rates or increases over an explicit time window:

```promql
sum by(service) (increase(order_created_total[5m]))
```

Use `seasonal_baseline` when the metric has daily or weekly cycles.
