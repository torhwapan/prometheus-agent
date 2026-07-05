# Node Exporter Catalog

Read this file only when the selected pack includes `node_exporter`.

## Effective Defaults

- pack key: `node-fixed-inspection`
- pack title: `Host Fixed Inspection`
- range hours: `24`
- step seconds: `60`
- current window: `5m`

Use each metric's PromQL for both the instant query and the range query.

## Metrics

### `node_cpu_usage`

- name: `CPU Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `75`
- critical: `90`
- max value: `100`

```promql
100 - (avg by(job, instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

### `node_memory_usage`

- name: `Memory Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`, `time_to_limit`
- warning: `80`
- critical: `92`
- max value: `100`

```promql
100 * (1 - (max by(job, instance) (node_memory_MemAvailable_bytes) / max by(job, instance) (node_memory_MemTotal_bytes)))
```

### `node_filesystem_usage`

- name: `Filesystem Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`, `mountpoint`, `device`
- methods: `threshold`, `sustained_growth`, `time_to_limit`
- warning: `80`
- critical: `90`
- max value: `100`

```promql
(1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay",mountpoint!~"/run.*"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay",mountpoint!~"/run.*"})) * 100
```

### `node_filesystem_inode_usage`

- name: `Filesystem Inode Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`, `mountpoint`, `device`
- methods: `threshold`, `sustained_growth`, `time_to_limit`
- warning: `80`
- critical: `90`
- max value: `100`

```promql
(1 - (node_filesystem_files_free{fstype!~"tmpfs|overlay",mountpoint!~"/run.*"} / node_filesystem_files{fstype!~"tmpfs|overlay",mountpoint!~"/run.*"})) * 100
```

### `node_disk_io_util`

- name: `Disk IO Utilization`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`, `device`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `70`
- critical: `90`
- max value: `100`

```promql
rate(node_disk_io_time_seconds_total{device!~"loop.*|ram.*"}[5m]) * 100
```

### `node_disk_read_bytes_rate`

- name: `Disk Read Throughput`
- value type: `number`
- unit: `B/s`
- direction: `higher_is_bad`
- labels: `job`, `instance`, `device`
- methods: `burst`, `sustained_growth`

```promql
rate(node_disk_read_bytes_total{device!~"loop.*|ram.*"}[5m])
```

### `node_disk_written_bytes_rate`

- name: `Disk Write Throughput`
- value type: `number`
- unit: `B/s`
- direction: `higher_is_bad`
- labels: `job`, `instance`, `device`
- methods: `burst`, `sustained_growth`

```promql
rate(node_disk_written_bytes_total{device!~"loop.*|ram.*"}[5m])
```

### `node_network_receive_bytes_rate`

- name: `Network Receive Throughput`
- value type: `number`
- unit: `B/s`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `burst`, `sustained_growth`

```promql
sum by(job, instance) (rate(node_network_receive_bytes_total{device!~"lo|docker.*|veth.*|br.*|cni.*"}[5m]))
```

### `node_network_transmit_bytes_rate`

- name: `Network Transmit Throughput`
- value type: `number`
- unit: `B/s`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `burst`, `sustained_growth`

```promql
sum by(job, instance) (rate(node_network_transmit_bytes_total{device!~"lo|docker.*|veth.*|br.*|cni.*"}[5m]))
```
