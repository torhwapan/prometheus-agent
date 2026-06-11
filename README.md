# Prometheus Inspection Agent

Python toolkit for a predictive Prometheus inspection workflow.

It provides three capabilities that can be exposed as tools in an AI platform:

- Query Prometheus range data with PromQL.
- Analyze time series for threshold breaches and near-future risk.
- Generate a standalone HTML inspection report.

## Quick Start

```powershell
python -m prometheus_agent --config config.example.json --output report.html
```

The config file is JSON. The important fields for each item are:

- `promql`: PromQL range query.
- `direction`: `higher_is_bad` or `lower_is_bad`.
- `warning` and `critical`: threshold values.
- `unit`: display unit in the report.

## AI Platform Integration

Use these functions as platform tools or workflow steps:

```python
from prometheus_agent import query_prometheus_range, analyze_item, generate_html_report, run_inspection
```

End-to-end usage:

```python
payload = run_inspection("config.example.json", output_path="report.html")
```

The returned payload contains:

- `result`: JSON-friendly structured inspection result.
- `report_path`: output file path when provided.
- `html`: HTML string when no output path is provided.

If the platform already handles scheduling, use `run_inspection` inside the
scheduled workflow. If the platform handles querying and analysis as separate
steps, use `query_prometheus_range`, then pass the returned series to
`analyze_item`, and finally pass the assembled `InspectionResult` to
`generate_html_report`.

## Analysis Method

For each returned Prometheus series, the analyzer computes:

- latest value
- average, min, max, p95
- linear trend slope per hour
- forecast value at `inspection.forecast_hours`
- estimated time to warning and critical threshold

Severity levels:

- `critical`: current value or forecast crosses the critical threshold.
- `warning`: current value or forecast crosses the warning threshold.
- `info`: bad trend consumes at least 50% of the remaining warning margin.
- `ok`: current and forecast values remain healthy.
- `unknown`: no data, query failure, or too few samples.

## Tests

```powershell
python -m unittest
```
