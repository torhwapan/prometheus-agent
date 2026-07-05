# HTTP Workflow

Use direct Prometheus HTTP API calls, following the same style as the generic `prometheus` skill.

## Discovery Endpoints

Use these endpoints first:

```bash
curl "<prometheus>/api/v1/label/job/values"
curl "<prometheus>/api/v1/targets"
```

PowerShell form:

```powershell
Invoke-RestMethod -Uri "<prometheus>/api/v1/label/job/values"
Invoke-RestMethod -Uri "<prometheus>/api/v1/targets"
```

## Query Endpoints

Instant query:

```bash
curl --get "<prometheus>/api/v1/query" --data-urlencode "query=<promql>" --data-urlencode "time=<unix-ts>"
```

Range query:

```bash
curl --get "<prometheus>/api/v1/query_range" --data-urlencode "query=<promql>" --data-urlencode "start=<unix-ts>" --data-urlencode "end=<unix-ts>" --data-urlencode "step=<seconds>"
```

PowerShell form:

```powershell
Invoke-RestMethod -Uri "<prometheus>/api/v1/query?query=<escaped-promql>&time=<unix-ts>"
Invoke-RestMethod -Uri "<prometheus>/api/v1/query_range?query=<escaped-promql>&start=<unix-ts>&end=<unix-ts>&step=<seconds>"
```

## Response Handling

- Expect JSON with top-level `status`.
- Read query results from `data.result`.
- Treat non-`success` responses as query errors.
- Keep current-query and range-query failures separately so fallback logic can explain which stage failed.

## Instance Filter Rule

When the user narrows inspection to one instance, apply the same deterministic rewrite that `planner.py` uses:

1. Build the matcher as `instance=~".*<escaped-instance>.*"`.
2. If the PromQL contains `{`, inject the matcher into the first selector by replacing the first `{` with `{instance=~"...",`.
3. If the query has no `{` and is a bare metric name, rewrite to `metric{instance=~"..."}`
4. If the query cannot be safely rewritten by this simple rule, leave it unchanged and mention the limitation in warnings.

Escaping rule:

- replace `\` with `\\`
- replace `"` with `\"`

## Time Defaults

- Use the report generation time as the shared `end`.
- Use the pack default or metric override for `range_hours`.
- Use the pack default or metric override for `step_seconds`.
- Use the pack default or metric override for `current_window`.
- Replace `[5m]` in the fixed PromQL with the metric's effective current window.

## Query Execution Pattern

For each selected metric:

1. Build the effective `current_window`, `range_hours`, and `step_seconds`.
2. Build the instant query with the metric's fixed PromQL.
3. Build the range query with the same fixed PromQL.
4. Execute both queries.
5. Keep labels and values from every returned series.
6. Match instant-query series to range-query series by the full label set.

## Warning Cases

Record warnings when:

- requested jobs are unsupported
- no supported jobs are discovered
- the instance filter could not be applied safely
- AI summary is skipped because no LLM settings were provided
- AI enrichment fails after deterministic analysis succeeded
