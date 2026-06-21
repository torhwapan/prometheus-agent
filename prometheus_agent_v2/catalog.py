"""Configured v2 metric catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .models import MetricSpec


DEFAULT_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "node_exporter": [
        {
            "id": "node_cpu_usage",
            "name": "CPU Usage",
            "description": "Host CPU non-idle usage.",
            "current_promql": "100 - (avg by(job, instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "range_promql": "100 - (avg by(job, instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 75,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "node_memory_usage",
            "name": "Memory Usage",
            "description": "Host memory usage based on MemAvailable.",
            "current_promql": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
            "range_promql": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth", "time_to_limit"],
            "warning": 80,
            "critical": 92,
            "max_value": 100,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "node_filesystem_usage",
            "name": "Filesystem Usage",
            "description": "Filesystem capacity usage by mount point.",
            "current_promql": "(1 - (node_filesystem_avail_bytes{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"} / node_filesystem_size_bytes{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"})) * 100",
            "range_promql": "(1 - (node_filesystem_avail_bytes{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"} / node_filesystem_size_bytes{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"})) * 100",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth", "time_to_limit"],
            "warning": 80,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance", "mountpoint", "device"],
        },
        {
            "id": "node_filesystem_inode_usage",
            "name": "Filesystem Inode Usage",
            "description": "Filesystem inode usage by mount point.",
            "current_promql": "(1 - (node_filesystem_files_free{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"} / node_filesystem_files{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"})) * 100",
            "range_promql": "(1 - (node_filesystem_files_free{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"} / node_filesystem_files{fstype!~\"tmpfs|overlay\",mountpoint!~\"/run.*\"})) * 100",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth", "time_to_limit"],
            "warning": 80,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance", "mountpoint", "device"],
        },
        {
            "id": "node_disk_io_util",
            "name": "Disk IO Utilization",
            "description": "Disk busy time ratio by device.",
            "current_promql": "rate(node_disk_io_time_seconds_total{device!~\"loop.*|ram.*\"}[5m]) * 100",
            "range_promql": "rate(node_disk_io_time_seconds_total{device!~\"loop.*|ram.*\"}[5m]) * 100",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 70,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance", "device"],
        },
    ],
    "java_jmx": [
        {
            "id": "jvm_process_cpu_usage",
            "name": "JVM Process CPU Usage",
            "description": "Java process CPU usage percentage.",
            "current_promql": "(avg by(job, instance) (java_lang_OperatingSystem_ProcessCpuLoad{job=\"java_jmx\"} * 100)) or (avg by(job, instance) (process_cpu_usage{job=\"java_jmx\"} * 100))",
            "range_promql": "(avg by(job, instance) (java_lang_OperatingSystem_ProcessCpuLoad{job=\"java_jmx\"} * 100)) or (avg by(job, instance) (process_cpu_usage{job=\"java_jmx\"} * 100))",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 70,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "jvm_heap_usage",
            "name": "JVM Heap Usage",
            "description": "JVM heap used percentage.",
            "current_promql": "100 * ((sum by(job, instance) (jvm_memory_bytes_used{job=\"java_jmx\",area=\"heap\"})) or (sum by(job, instance) (jvm_memory_used_bytes{job=\"java_jmx\",area=\"heap\"})) or (sum by(job, instance) (java_lang_Memory_HeapMemoryUsage_used{job=\"java_jmx\"}))) / ((sum by(job, instance) (jvm_memory_bytes_max{job=\"java_jmx\",area=\"heap\"} > 0)) or (sum by(job, instance) (jvm_memory_max_bytes{job=\"java_jmx\",area=\"heap\"} > 0)) or (sum by(job, instance) (java_lang_Memory_HeapMemoryUsage_max{job=\"java_jmx\"} > 0)))",
            "range_promql": "100 * ((sum by(job, instance) (jvm_memory_bytes_used{job=\"java_jmx\",area=\"heap\"})) or (sum by(job, instance) (jvm_memory_used_bytes{job=\"java_jmx\",area=\"heap\"})) or (sum by(job, instance) (java_lang_Memory_HeapMemoryUsage_used{job=\"java_jmx\"}))) / ((sum by(job, instance) (jvm_memory_bytes_max{job=\"java_jmx\",area=\"heap\"} > 0)) or (sum by(job, instance) (jvm_memory_max_bytes{job=\"java_jmx\",area=\"heap\"} > 0)) or (sum by(job, instance) (java_lang_Memory_HeapMemoryUsage_max{job=\"java_jmx\"} > 0)))",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth", "time_to_limit"],
            "warning": 75,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "jvm_gc_time_rate",
            "name": "JVM GC Time Rate",
            "description": "Seconds spent in GC per second.",
            "current_promql": "(sum by(job, instance) (rate(jvm_gc_collection_seconds_sum{job=\"java_jmx\"}[5m]))) or (sum by(job, instance) (rate(jvm_gc_pause_seconds_sum{job=\"java_jmx\"}[5m]))) or (sum by(job, instance) (rate(java_lang_GarbageCollector_CollectionTime{job=\"java_jmx\"}[5m]) / 1000))",
            "range_promql": "(sum by(job, instance) (rate(jvm_gc_collection_seconds_sum{job=\"java_jmx\"}[5m]))) or (sum by(job, instance) (rate(jvm_gc_pause_seconds_sum{job=\"java_jmx\"}[5m]))) or (sum by(job, instance) (rate(java_lang_GarbageCollector_CollectionTime{job=\"java_jmx\"}[5m]) / 1000))",
            "value_type": "number",
            "unit": "s/s",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 0.05,
            "critical": 0.2,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "jvm_threads_live",
            "name": "JVM Live Threads",
            "description": "JVM live thread count.",
            "current_promql": "(max by(job, instance) (jvm_threads_current{job=\"java_jmx\"})) or (max by(job, instance) (jvm_threads_live_threads{job=\"java_jmx\"})) or (max by(job, instance) (java_lang_Threading_ThreadCount{job=\"java_jmx\"}))",
            "range_promql": "(max by(job, instance) (jvm_threads_current{job=\"java_jmx\"})) or (max by(job, instance) (jvm_threads_live_threads{job=\"java_jmx\"})) or (max by(job, instance) (java_lang_Threading_ThreadCount{job=\"java_jmx\"}))",
            "value_type": "number",
            "unit": "",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 400,
            "critical": 800,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "jvm_fd_usage",
            "name": "JVM Open File Descriptor Usage",
            "description": "Java process open file descriptor usage percentage.",
            "current_promql": "100 * ((max by(job, instance) (java_lang_OperatingSystem_OpenFileDescriptorCount{job=\"java_jmx\"})) or (max by(job, instance) (process_open_fds{job=\"java_jmx\"}))) / ((max by(job, instance) (java_lang_OperatingSystem_MaxFileDescriptorCount{job=\"java_jmx\"} > 0)) or (max by(job, instance) (process_max_fds{job=\"java_jmx\"} > 0)))",
            "range_promql": "100 * ((max by(job, instance) (java_lang_OperatingSystem_OpenFileDescriptorCount{job=\"java_jmx\"})) or (max by(job, instance) (process_open_fds{job=\"java_jmx\"}))) / ((max by(job, instance) (java_lang_OperatingSystem_MaxFileDescriptorCount{job=\"java_jmx\"} > 0)) or (max by(job, instance) (process_max_fds{job=\"java_jmx\"} > 0)))",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth", "time_to_limit"],
            "warning": 60,
            "critical": 80,
            "max_value": 100,
            "labels_to_keep": ["job", "instance"],
        },
    ],
    "redis_exporter": [
        {
            "id": "redis_up",
            "name": "Redis Up",
            "description": "Redis exporter availability.",
            "current_promql": "redis_up{job=\"redis_exporter\"}",
            "range_promql": "redis_up{job=\"redis_exporter\"}",
            "value_type": "number",
            "unit": "",
            "direction": "lower_is_bad",
            "analysis_methods": ["threshold"],
            "warning": 1,
            "critical": 0,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "redis_memory_usage",
            "name": "Redis Memory Usage",
            "description": "Redis memory used percentage of maxmemory or total system memory.",
            "current_promql": "100 * (sum by(job, instance) (redis_memory_used_bytes{job=\"redis_exporter\"})) / ((sum by(job, instance) (redis_memory_max_bytes{job=\"redis_exporter\"} > 0)) or (sum by(job, instance) (redis_config_maxmemory{job=\"redis_exporter\"} > 0)) or (sum by(job, instance) (redis_total_system_memory_bytes{job=\"redis_exporter\"})))",
            "range_promql": "100 * (sum by(job, instance) (redis_memory_used_bytes{job=\"redis_exporter\"})) / ((sum by(job, instance) (redis_memory_max_bytes{job=\"redis_exporter\"} > 0)) or (sum by(job, instance) (redis_config_maxmemory{job=\"redis_exporter\"} > 0)) or (sum by(job, instance) (redis_total_system_memory_bytes{job=\"redis_exporter\"})))",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth", "time_to_limit"],
            "warning": 75,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "redis_connected_clients",
            "name": "Redis Connected Clients",
            "description": "Connected Redis clients.",
            "current_promql": "redis_connected_clients{job=\"redis_exporter\"}",
            "range_promql": "redis_connected_clients{job=\"redis_exporter\"}",
            "value_type": "number",
            "unit": "",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 800,
            "critical": 1000,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "redis_blocked_clients",
            "name": "Redis Blocked Clients",
            "description": "Blocked Redis clients waiting on slow operations.",
            "current_promql": "redis_blocked_clients{job=\"redis_exporter\"}",
            "range_promql": "redis_blocked_clients{job=\"redis_exporter\"}",
            "value_type": "number",
            "unit": "",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 1,
            "critical": 5,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "redis_mem_fragmentation_ratio",
            "name": "Redis Memory Fragmentation Ratio",
            "description": "Redis allocator memory fragmentation ratio.",
            "current_promql": "redis_mem_fragmentation_ratio{job=\"redis_exporter\"}",
            "range_promql": "redis_mem_fragmentation_ratio{job=\"redis_exporter\"}",
            "value_type": "number",
            "unit": "",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth"],
            "warning": 1.5,
            "critical": 2,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "redis_evicted_keys_rate",
            "name": "Redis Evicted Keys Rate",
            "description": "Rate of evicted keys.",
            "current_promql": "rate(redis_evicted_keys_total{job=\"redis_exporter\"}[5m])",
            "range_promql": "rate(redis_evicted_keys_total{job=\"redis_exporter\"}[5m])",
            "value_type": "number",
            "unit": "/s",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst"],
            "warning": 1,
            "critical": 10,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "redis_rejected_connections_rate",
            "name": "Redis Rejected Connections Rate",
            "description": "Rate of rejected client connections.",
            "current_promql": "rate(redis_rejected_connections_total{job=\"redis_exporter\"}[5m])",
            "range_promql": "rate(redis_rejected_connections_total{job=\"redis_exporter\"}[5m])",
            "value_type": "number",
            "unit": "/s",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "burst", "sustained_growth"],
            "warning": 1,
            "critical": 5,
            "labels_to_keep": ["job", "instance"],
        },
    ],
    "rabbitmq_exporter": [
        {
            "id": "rabbitmq_module_up",
            "name": "RabbitMQ Module Up",
            "description": "RabbitMQ exporter module availability.",
            "current_promql": "min by(job, instance) (rabbitmq_module_up{job=\"rabbitmq_exporter\"})",
            "range_promql": "min by(job, instance) (rabbitmq_module_up{job=\"rabbitmq_exporter\"})",
            "value_type": "number",
            "unit": "",
            "direction": "lower_is_bad",
            "analysis_methods": ["threshold"],
            "warning": 1,
            "critical": 0,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "rabbitmq_node_mem_usage",
            "name": "RabbitMQ Node Memory Usage",
            "description": "RabbitMQ node memory usage percentage of the memory watermark.",
            "current_promql": "100 * rabbitmq_node_mem_used{job=\"rabbitmq_exporter\"} / clamp_min(rabbitmq_node_mem_limit{job=\"rabbitmq_exporter\"}, 1)",
            "range_promql": "100 * rabbitmq_node_mem_used{job=\"rabbitmq_exporter\"} / clamp_min(rabbitmq_node_mem_limit{job=\"rabbitmq_exporter\"}, 1)",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth", "time_to_limit"],
            "warning": 75,
            "critical": 90,
            "max_value": 100,
            "labels_to_keep": ["job", "instance", "cluster", "node"],
        },
        {
            "id": "rabbitmq_fd_usage",
            "name": "RabbitMQ File Descriptor Usage",
            "description": "RabbitMQ node file descriptor usage percentage.",
            "current_promql": "100 * rabbitmq_fd_used{job=\"rabbitmq_exporter\"} / clamp_min(rabbitmq_fd_used{job=\"rabbitmq_exporter\"} + rabbitmq_fd_available{job=\"rabbitmq_exporter\"}, 1)",
            "range_promql": "100 * rabbitmq_fd_used{job=\"rabbitmq_exporter\"} / clamp_min(rabbitmq_fd_used{job=\"rabbitmq_exporter\"} + rabbitmq_fd_available{job=\"rabbitmq_exporter\"}, 1)",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth", "time_to_limit"],
            "warning": 70,
            "critical": 85,
            "max_value": 100,
            "labels_to_keep": ["job", "instance"],
        },
        {
            "id": "rabbitmq_disk_free_limit_pressure",
            "name": "RabbitMQ Disk Free Limit Pressure",
            "description": "Pressure relative to RabbitMQ disk free alarm limit.",
            "current_promql": "100 * rabbitmq_node_disk_free_limit{job=\"rabbitmq_exporter\"} / clamp_min(rabbitmq_node_disk_free{job=\"rabbitmq_exporter\"}, 1)",
            "range_promql": "100 * rabbitmq_node_disk_free_limit{job=\"rabbitmq_exporter\"} / clamp_min(rabbitmq_node_disk_free{job=\"rabbitmq_exporter\"}, 1)",
            "value_type": "percent",
            "unit": "%",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold", "sustained_growth"],
            "warning": 80,
            "critical": 100,
            "labels_to_keep": ["job", "instance", "cluster", "node"],
        },
        {
            "id": "rabbitmq_queue_consumer_utilisation",
            "name": "RabbitMQ Queue Consumer Utilisation",
            "description": "Queue consumer utilisation percentage; low values indicate consumer bottlenecks.",
            "current_promql": "rabbitmq_queue_consumer_utilisation{job=\"rabbitmq_exporter\"} * 100",
            "range_promql": "rabbitmq_queue_consumer_utilisation{job=\"rabbitmq_exporter\"} * 100",
            "value_type": "percent",
            "unit": "%",
            "direction": "lower_is_bad",
            "analysis_methods": ["threshold"],
            "warning": 70,
            "critical": 40,
            "max_value": 100,
            "labels_to_keep": ["job", "instance", "cluster", "vhost", "queue"],
        },
        {
            "id": "rabbitmq_node_mem_alarm",
            "name": "RabbitMQ Node Memory Alarm",
            "description": "RabbitMQ node memory alarm status.",
            "current_promql": "rabbitmq_node_mem_alarm{job=\"rabbitmq_exporter\"}",
            "range_promql": "rabbitmq_node_mem_alarm{job=\"rabbitmq_exporter\"}",
            "value_type": "number",
            "unit": "",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold"],
            "warning": 1,
            "critical": 1,
            "max_value": 1,
            "labels_to_keep": ["job", "instance", "cluster", "node"],
        },
        {
            "id": "rabbitmq_node_disk_free_alarm",
            "name": "RabbitMQ Node Disk Free Alarm",
            "description": "RabbitMQ node disk free alarm status.",
            "current_promql": "rabbitmq_node_disk_free_alarm{job=\"rabbitmq_exporter\"}",
            "range_promql": "rabbitmq_node_disk_free_alarm{job=\"rabbitmq_exporter\"}",
            "value_type": "number",
            "unit": "",
            "direction": "higher_is_bad",
            "analysis_methods": ["threshold"],
            "warning": 1,
            "critical": 1,
            "max_value": 1,
            "labels_to_keep": ["job", "instance", "cluster", "node"],
        },
    ],
}


JOB_ALIASES = {
    "node": "node_exporter",
    "node-exporter": "node_exporter",
    "node_exporter": "node_exporter",
    "node_exporer": "node_exporter",
    "linux": "node_exporter",
    "host": "node_exporter",
    "server": "node_exporter",
    "jvm": "java_jmx",
    "java": "java_jmx",
    "spring": "java_jmx",
    "java_jmx": "java_jmx",
    "redis": "redis_exporter",
    "redis_exporter": "redis_exporter",
    "mq": "rabbitmq_exporter",
    "rabbitmq": "rabbitmq_exporter",
    "rabbitmq_exporter": "rabbitmq_exporter",
}


def load_catalog(path: Optional[str] = None) -> Dict[str, List[MetricSpec]]:
    raw = DEFAULT_CATALOG if path is None else _load_json(path)
    catalog: Dict[str, List[MetricSpec]] = {}
    for job, items in raw.items():
        normalized_job = normalize_job(job)
        catalog[normalized_job] = [_to_metric_spec(normalized_job, item) for item in items]
    return catalog


def select_specs(
    catalog: Mapping[str, Sequence[MetricSpec]],
    job: Optional[str] = None,
    metric_ids: Optional[Sequence[str]] = None,
) -> List[MetricSpec]:
    jobs = [normalize_job(job)] if job else list(catalog.keys())
    wanted = set(metric_ids or [])
    specs: List[MetricSpec] = []
    for item_job in jobs:
        for spec in catalog.get(item_job, []):
            if wanted and spec.id not in wanted:
                continue
            specs.append(spec)
    return specs


def normalize_job(job: Optional[str]) -> str:
    if not job:
        return ""
    normalized = job.strip().lower()
    return JOB_ALIASES.get(normalized, normalized)


def catalog_summary(catalog: Mapping[str, Sequence[MetricSpec]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        job: [
            {
                "id": spec.id,
                "name": spec.name,
                "value_type": spec.value_type,
                "analysis_methods": spec.analysis_methods,
                "unit": spec.unit,
            }
            for spec in specs
        ]
        for job, specs in catalog.items()
    }


def _load_json(path: str) -> Dict[str, List[Dict[str, Any]]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _to_metric_spec(job: str, item: Mapping[str, Any]) -> MetricSpec:
    return MetricSpec(
        job=job,
        id=str(item["id"]),
        name=str(item.get("name") or item["id"]),
        description=str(item.get("description") or ""),
        current_promql=str(item.get("current_promql") or item.get("promql") or ""),
        range_promql=str(item.get("range_promql") or item.get("promql") or ""),
        value_type=str(item.get("value_type") or "number"),
        unit=str(item.get("unit") or ""),
        direction=str(item.get("direction") or "higher_is_bad"),
        analysis_methods=[str(method) for method in item.get("analysis_methods", [])],
        warning=_optional_float(item.get("warning")),
        critical=_optional_float(item.get("critical")),
        max_value=_optional_float(item.get("max_value")),
        labels_to_keep=[str(label) for label in item.get("labels_to_keep", [])],
    )


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)
