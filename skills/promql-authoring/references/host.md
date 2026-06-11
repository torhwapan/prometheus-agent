# Host PromQL Patterns

Use these patterns for node-exporter style metrics.

## CPU Usage

Current and trend:

```promql
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

Use `threshold_trend`, `higher_is_bad`, unit `%`.

## Memory Usage

```promql
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
```

Use `threshold_trend`, `higher_is_bad`, unit `%`.

## Filesystem Usage

```promql
(1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay",mountpoint!~"/run.*"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay",mountpoint!~"/run.*"})) * 100
```

Keep `instance`, `mountpoint`, and `device`.

## Inode Usage

```promql
(1 - (node_filesystem_files_free{fstype!~"tmpfs|overlay"} / node_filesystem_files{fstype!~"tmpfs|overlay"})) * 100
```

## Load

```promql
node_load1
```

Compare with CPU core count when available:

```promql
node_load1 / count by(instance) (node_cpu_seconds_total{mode="idle"})
```
