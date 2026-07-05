# RabbitMQ Exporter Catalog

Read this file only when the selected pack includes `rabbitmq_exporter`.

## Effective Defaults

- pack key: `rabbitmq-fixed-inspection`
- pack title: `RabbitMQ Fixed Inspection`
- range hours: `24`
- step seconds: `60`
- current window: `5m`

Use each metric's PromQL for both the instant query and the range query, unless a metric override is listed.

## Metrics

### `rabbitmq_module_up`

- name: `RabbitMQ Module Up`
- value type: `number`
- unit: ``
- direction: `lower_is_bad`
- labels: `job`, `instance`
- methods: `threshold`
- warning: `1`
- critical: `0`

```promql
min by(job, instance) (rabbitmq_module_up{job="rabbitmq_exporter"})
```

### `rabbitmq_node_mem_usage`

- name: `RabbitMQ Node Memory Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`, `cluster`, `node`
- methods: `threshold`, `sustained_growth`, `time_to_limit`
- warning: `75`
- critical: `90`
- max value: `100`

```promql
100 * rabbitmq_node_mem_used{job="rabbitmq_exporter"} / clamp_min(rabbitmq_node_mem_limit{job="rabbitmq_exporter"}, 1)
```

### `rabbitmq_fd_usage`

- name: `RabbitMQ File Descriptor Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `sustained_growth`, `time_to_limit`
- warning: `70`
- critical: `85`
- max value: `100`

```promql
100 * rabbitmq_fd_used{job="rabbitmq_exporter"} / clamp_min(rabbitmq_fd_used{job="rabbitmq_exporter"} + rabbitmq_fd_available{job="rabbitmq_exporter"}, 1)
```

### `rabbitmq_disk_free_limit_pressure`

- name: `RabbitMQ Disk Free Limit Pressure`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`, `cluster`, `node`
- methods: `threshold`, `sustained_growth`
- warning: `80`
- critical: `100`

```promql
100 * rabbitmq_node_disk_free_limit{job="rabbitmq_exporter"} / clamp_min(rabbitmq_node_disk_free{job="rabbitmq_exporter"}, 1)
```

### `rabbitmq_queue_consumer_utilisation`

- name: `RabbitMQ Queue Consumer Utilisation`
- value type: `percent`
- unit: `%`
- direction: `lower_is_bad`
- labels: `job`, `instance`, `cluster`, `vhost`, `queue`
- methods: `threshold`
- warning: `70`
- critical: `40`
- max value: `100`
- current window override: `10m`
- range hours override: `6`
- step seconds override: `120`

```promql
rabbitmq_queue_consumer_utilisation{job="rabbitmq_exporter"} * 100
```

### `rabbitmq_node_mem_alarm`

- name: `RabbitMQ Node Memory Alarm`
- value type: `number`
- unit: ``
- direction: `higher_is_bad`
- labels: `job`, `instance`, `cluster`, `node`
- methods: `threshold`
- warning: `1`
- critical: `1`
- max value: `1`

```promql
rabbitmq_node_mem_alarm{job="rabbitmq_exporter"}
```

### `rabbitmq_node_disk_free_alarm`

- name: `RabbitMQ Node Disk Free Alarm`
- value type: `number`
- unit: ``
- direction: `higher_is_bad`
- labels: `job`, `instance`, `cluster`, `node`
- methods: `threshold`
- warning: `1`
- critical: `1`
- max value: `1`

```promql
rabbitmq_node_disk_free_alarm{job="rabbitmq_exporter"}
```
