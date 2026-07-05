# Java JMX Catalog

Read this file only when the selected pack includes `java_jmx`.

## Effective Defaults

- pack key: `jvm-fixed-inspection`
- pack title: `JVM Fixed Inspection`
- range hours: `24`
- step seconds: `60`
- current window: `5m`

Use each metric's PromQL for both the instant query and the range query.

## Metrics

### `jvm_process_cpu_usage`

- name: `JVM Process CPU Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `70`
- critical: `90`
- max value: `100`

```promql
(avg by(job, instance) (java_lang_OperatingSystem_ProcessCpuLoad{job="java_jmx"} * 100)) or (avg by(job, instance) (process_cpu_usage{job="java_jmx"} * 100))
```

### `jvm_heap_usage`

- name: `JVM Heap Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `sustained_growth`, `time_to_limit`
- warning: `75`
- critical: `90`
- max value: `100`

```promql
100 * ((sum by(job, instance) (jvm_memory_bytes_used{job="java_jmx",area="heap"})) or (sum by(job, instance) (jvm_memory_used_bytes{job="java_jmx",area="heap"})) or (sum by(job, instance) (java_lang_Memory_HeapMemoryUsage_used{job="java_jmx"}))) / ((sum by(job, instance) (jvm_memory_bytes_max{job="java_jmx",area="heap"} > 0)) or (sum by(job, instance) (jvm_memory_max_bytes{job="java_jmx",area="heap"} > 0)) or (sum by(job, instance) (java_lang_Memory_HeapMemoryUsage_max{job="java_jmx"} > 0)))
```

### `jvm_gc_time_rate`

- name: `JVM GC Time Rate`
- value type: `number`
- unit: `s/s`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `0.05`
- critical: `0.2`

```promql
(sum by(job, instance) (rate(jvm_gc_collection_seconds_sum{job="java_jmx"}[5m]))) or (sum by(job, instance) (rate(jvm_gc_pause_seconds_sum{job="java_jmx"}[5m]))) or (sum by(job, instance) (rate(java_lang_GarbageCollector_CollectionTime{job="java_jmx"}[5m]) / 1000))
```

### `jvm_gc_count_increase`

- name: `JVM GC Count Increase`
- value type: `number`
- unit: `count`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `50`
- critical: `200`

```promql
(sum by(job, instance) (increase(jvm_gc_collection_seconds_count{job="java_jmx"}[5m]))) or (sum by(job, instance) (increase(jvm_gc_pause_seconds_count{job="java_jmx"}[5m]))) or (sum by(job, instance) (increase(java_lang_GarbageCollector_CollectionCount{job="java_jmx"}[5m])))
```

### `jvm_threads_live`

- name: `JVM Live Threads`
- value type: `number`
- unit: ``
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `burst`, `sustained_growth`
- warning: `400`
- critical: `800`

```promql
(max by(job, instance) (jvm_threads_current{job="java_jmx"})) or (max by(job, instance) (jvm_threads_live_threads{job="java_jmx"})) or (max by(job, instance) (java_lang_Threading_ThreadCount{job="java_jmx"}))
```

### `jvm_fd_usage`

- name: `JVM Open File Descriptor Usage`
- value type: `percent`
- unit: `%`
- direction: `higher_is_bad`
- labels: `job`, `instance`
- methods: `threshold`, `sustained_growth`, `time_to_limit`
- warning: `60`
- critical: `80`
- max value: `100`

```promql
100 * ((max by(job, instance) (java_lang_OperatingSystem_OpenFileDescriptorCount{job="java_jmx"})) or (max by(job, instance) (process_open_fds{job="java_jmx"}))) / ((max by(job, instance) (java_lang_OperatingSystem_MaxFileDescriptorCount{job="java_jmx"} > 0)) or (max by(job, instance) (process_max_fds{job="java_jmx"} > 0)))
```
