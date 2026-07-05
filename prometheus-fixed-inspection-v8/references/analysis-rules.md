# Analysis Rules

Apply these rules exactly. This reference describes the deterministic rule engine for this skill.

## Severity Order

Use this order for comparisons and final sorting:

| Severity | Rank |
| --- | ---: |
| `ok` | 0 |
| `info` | 1 |
| `warning` | 2 |
| `critical` | 3 |
| `unknown` | 4 |

When combining severities, choose the highest rank.

## Input Model

Each finding is based on:

- one metric spec
- one label set
- one current value from the instant query when available
- one time series from the range query when available
- the metric's thresholds, direction, limits, and analysis methods

## No Data Rule

If neither the instant query nor the range query returns usable series for the task:

- emit one `unknown` finding
- use empty labels
- explain that the task returned no usable time-series data

## Current-Only Fallback

If the range query fails or returns no series, but the instant query returns a value:

1. classify only from threshold rules
2. mark the reasoning as current-only fallback
3. include the range-query error message when available

Threshold logic:

- for `higher_is_bad`
  - `critical` if `value >= critical`
  - `warning` if `value >= warning`
  - else `ok`
- for `lower_is_bad`
  - `critical` if `value <= critical`
  - `warning` if `value <= warning`
  - else `ok`

## Range-Series Analysis

When a range series is available:

1. discard non-finite samples
2. if fewer than 4 samples remain, emit `unknown`
3. otherwise compute:
   - `current`
   - `min`
   - `max`
   - `avg`
   - `p95`
   - `slope_per_hour`
   - `forecast_24h = current + slope_per_hour * 24`

Use the instant current value when the same label set exists there. Otherwise use the last range sample.

## Threshold Severity

Calculate `threshold_severity` from the current value using the threshold rules above.

## Forecast Severity

Calculate `forecast_severity` from `forecast_24h` with the same threshold rules.

## Burst Rule

Apply only when the metric includes `burst`.

1. split the series into early half and late half
2. compute the average of each half
3. if the relative change is at least `0.5` and the late half moves in the bad direction, mark `burst = true`

Bad direction:

- `higher_is_bad`: late average is higher
- `lower_is_bad`: late average is lower

Burst raises severity to at least `warning`.

## Sustained Deterioration Rule

Apply only when the metric includes `sustained_growth`.

1. compare each adjacent pair of samples
2. count a bad step when the next sample moves in the bad direction
3. require at least 80 percent of steps to be bad
4. require the final sample to be worse than the first sample

Bad direction:

- `higher_is_bad`: `after >= before`
- `lower_is_bad`: `after <= before`

Sustained deterioration raises severity to at least `info`.

## Time-To-Limit Rule

Apply only when the metric includes `time_to_limit`.

For `higher_is_bad`:

- use `max_value` if present
- else use `critical`
- else use `warning`
- if `slope_per_hour <= 0`, no estimate
- if `current >= limit`, return `0`
- else `hours = (limit - current) / slope_per_hour`

For `lower_is_bad`:

- use `critical` if present, else `warning`
- if `slope_per_hour >= 0`, no estimate
- if `current <= limit`, return `0`
- else `hours = (limit - current) / slope_per_hour`

If the estimated time is finite and `<= 24`, raise severity to at least `warning`.

## Final Severity

Start from the highest of:

- `threshold_severity`
- `forecast_severity`

Then raise severity if:

- `burst` is true
- `sustained_deterioration` is true
- `time_to_limit_hours <= 24`

## Reasoning Text

The reason text should explain only triggered rules:

- threshold breach
- 24h forecast breach
- burst behavior
- sustained deterioration
- time to limit

If nothing is abnormal, say that no obvious threshold breach, deterioration, or burst was detected.

## Sorting

Sort findings descending by:

1. severity rank
2. job
3. instance
4. metric id
5. absolute current value

## Summary Counts

Return counts for:

- `critical`
- `warning`
- `info`
- `ok`
- `unknown`
