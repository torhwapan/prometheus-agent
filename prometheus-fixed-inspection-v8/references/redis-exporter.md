# Redis Exporter Catalog

Read this file only when the selected pack includes `redis_exporter`.

## Effective Defaults

- pack key: `redis-fixed-inspection`
- pack title: `Redis Fixed Inspection`
- range hours: `24`
- step seconds: `60`
- current window: `5m`

Use each metric's PromQL for both the instant query and the range query.

## Metrics

### `redis_up`

- name: `Redis Up`
- value type: `number`
- unit: ``
- direction: `lower_is_bad`
- labels: `job`, `instance`
- methods: `threshold`
- warning: `1`
- critical: `0`

```promql
redis_up{job="redis_exporter"}
```

### `redis_memory_usage`

- name: `Redis Memory Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`, `time_to_limit`
- warning: `75`
- critical: `90`
- max value: `100`

```promql
100 * (sum by(job, instance) (redis_memory_used_bytes{job="redis_exporter"})) / ((sum by(job, instance) (redis_memory_max_bytes{job="redis_exporter"} > 0)) or (sum by(job, instance) (redis_config_maxmemory{job="redis_exporter"} > 0)) or (sum by(job, instance) (redis_total_system_memory_bytes{job="redis_exporter"})))
```

### `redis_connected_clients`

- name: `Redis Connected Clients`
- value type: `number`
- unit: ``
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `800`
- critical: `1000`

```promql
redis_connected_clients{job="redis_exporter"}
```

### `redis_blocked_clients`

- name: `Redis Blocked Clients`
- value type: `number`
- unit: ``
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `1`
- critical: `5`

```promql
redis_blocked_clients{job="redis_exporter"}
```

### `redis_mem_fragmentation_ratio`

- name: `Redis Memory Fragmentation Ratio`
- value type: `number`
- unit: ``
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `sustained_growth`
- warning: `1.5`
- critical: `2`

```promql
redis_mem_fragmentation_ratio{job="redis_exporter"}
```

### `redis_evicted_keys_rate`

- name: `Redis Evicted Keys Rate`
- value type: `number`
- unit: `/s`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`
- warning: `1`
- critical: `10`

```promql
rate(redis_evicted_keys_total{job="redis_exporter"}[5m])
```

### `redis_rejected_connections_rate`

- name: `Redis Rejected Connections Rate`
- value type: `number`
- unit: `/s`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `1`
- critical: `5`

```promql
rate(redis_rejected_connections_total{job="redis_exporter"}[5m])
```
