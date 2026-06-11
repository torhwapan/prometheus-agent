# JVM PromQL Patterns

Metric names vary by exporter. Prefer Micrometer names when present, then fall back to JMX exporter names.

## Heap Usage

Micrometer:

```promql
sum by(job, instance) (jvm_memory_used_bytes{area="heap"}) / sum by(job, instance) (jvm_memory_max_bytes{area="heap"}) * 100
```

JMX exporter pattern:

```promql
sum by(job, instance) (jvm_memory_bytes_used{area="heap"}) / sum by(job, instance) (jvm_memory_bytes_max{area="heap"}) * 100
```

Use `jvm_memory` or `threshold_trend`, `higher_is_bad`, unit `%`.

## Non-Heap Usage

```promql
sum by(job, instance) (jvm_memory_used_bytes{area="nonheap"})
```

Use bytes unit if max is unavailable.

## GC Time Rate

Micrometer:

```promql
sum by(job, instance) (rate(jvm_gc_pause_seconds_sum[5m]))
```

Use `jvm_gc`, `higher_is_bad`, unit `s/s`.

## Thread Count

```promql
jvm_threads_live_threads
```

Use `threshold_trend`, `higher_is_bad`.

## Class Loading Churn

```promql
rate(jvm_classes_unloaded_classes_total[5m])
```

Use `rate_change` or `change_detection`.
