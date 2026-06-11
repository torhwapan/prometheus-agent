# Redis Core Metrics

## Core

- Redis up: exporter or Redis availability. Use `availability`.
- Memory usage percent: maxmemory pressure. Use `threshold_trend` or `growth_to_limit`.
- Memory used bytes: capacity trend when maxmemory is unavailable. Use `continuous_growth`.
- Evicted keys rate: cache pressure or memory policy impact. Use `rate_change`.
- Rejected connections rate: connection limit or overload. Use `error_rate`.
- Blocked clients: slow operation or blocking command risk. Use `threshold_trend`.
- Keyspace hit rate: cache effectiveness. Use `availability` with `lower_is_bad`.
- Connected clients: connection pressure. Use `threshold_trend`.

## Secondary

- Commands processed rate.
- Expired keys rate.
- Replication lag when Redis replication is in use.

## Interpretation Notes

Memory fragmentation ratio above normal can be risky even when used memory is not high. Eviction is not always an outage, but it is important for cache quality and should be highlighted.
