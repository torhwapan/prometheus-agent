# Business Metric Domains

Business metrics must be defined by service owners. Treat them as first-class only when the metric has a clear owner and business meaning.

## Common Core Metrics

- Error rate: failed requests or failed business operations. Use `error_rate`.
- Success rate: successful requests or operations. Use `availability`.
- Latency P95/P99: user experience and dependency pressure. Use `latency`.
- Traffic rate: QPS/TPS or operation rate. Use `seasonal_baseline`, `burst_detection`, or `rate_change`.
- Order/payment count: use `seasonal_baseline` when daily or weekly cycles exist.

## Notes

Do not mark low traffic as bad unless the metric has expected business volume or a historical baseline. Do not invent business thresholds; use catalog, Grafana alert rules, or explicit user input.
