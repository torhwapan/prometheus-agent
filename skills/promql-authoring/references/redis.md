# Redis PromQL Patterns

Metric names assume redis_exporter style metrics.

## Redis Up

```promql
redis_up
```

Use `availability`, `lower_is_bad`.

## Memory Usage Percent

```promql
redis_memory_used_bytes / redis_memory_max_bytes * 100
```

If `redis_memory_max_bytes` is zero or absent, analyze `redis_memory_used_bytes` as a numeric trend instead.

## Memory Fragmentation Ratio

```promql
redis_mem_fragmentation_ratio
```

Use `threshold_trend`, `higher_is_bad`.

## Connected Clients

```promql
redis_connected_clients
```

Use `threshold_trend`, `higher_is_bad`.

## Blocked Clients

```promql
redis_blocked_clients
```

Any sustained value above zero deserves attention.

## Evicted Keys Rate

```promql
rate(redis_evicted_keys_total[5m])
```

Use `error_rate` or `rate_change`, `higher_is_bad`.

## Rejected Connections Rate

```promql
rate(redis_rejected_connections_total[5m])
```

Use `error_rate`, `higher_is_bad`.

## Keyspace Hit Rate

```promql
rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m])) * 100
```

Use `availability` or `threshold_trend`, `lower_is_bad`.
