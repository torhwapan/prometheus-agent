"""Fixed metric catalog and inspection packs for V6."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from prometheus_agent_v2.catalog import DEFAULT_CATALOG as LEGACY_CATALOG

from .models import InspectionPack, MetricSpec


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


PACK_TEMPLATES = {
    "node_exporter": {
        "key": "node-fixed-inspection",
        "title": "主机资源固定巡检",
        "description": "检查 CPU、内存、磁盘、网络等主机基础资源指标。",
        "range_hours": 24.0,
        "step_seconds": 60,
        "current_window": "5m",
    },
    "java_jmx": {
        "key": "jvm-fixed-inspection",
        "title": "JVM 应用固定巡检",
        "description": "检查 JVM 进程 CPU、堆内存、GC、线程与文件句柄压力。",
        "range_hours": 24.0,
        "step_seconds": 60,
        "current_window": "5m",
    },
    "redis_exporter": {
        "key": "redis-fixed-inspection",
        "title": "Redis 固定巡检",
        "description": "检查 Redis 可用性、内存、连接、碎片率、淘汰和拒绝连接风险。",
        "range_hours": 24.0,
        "step_seconds": 60,
        "current_window": "5m",
    },
    "rabbitmq_exporter": {
        "key": "rabbitmq-fixed-inspection",
        "title": "RabbitMQ 固定巡检",
        "description": "检查 RabbitMQ 内存、磁盘、FD、消费利用率与告警状态。",
        "range_hours": 24.0,
        "step_seconds": 60,
        "current_window": "5m",
    },
}


JOB_ORDER = [
    "node_exporter",
    "java_jmx",
    "redis_exporter",
    "rabbitmq_exporter",
]


def normalize_job(job: Optional[str]) -> str:
    if not job:
        return ""
    normalized = str(job).strip().lower()
    return JOB_ALIASES.get(normalized, normalized)


def load_catalog() -> Dict[str, List[MetricSpec]]:
    catalog: Dict[str, List[MetricSpec]] = {}
    for job, items in LEGACY_CATALOG.items():
        normalized_job = normalize_job(job)
        catalog[normalized_job] = [_to_metric_spec(normalized_job, item) for item in items]
    return catalog


def build_default_packs(catalog: Mapping[str, Sequence[MetricSpec]] | None = None) -> List[InspectionPack]:
    catalog = catalog or load_catalog()
    packs: List[InspectionPack] = []
    for job in JOB_ORDER:
        specs = list(catalog.get(job, []))
        template = PACK_TEMPLATES.get(job)
        if not specs or template is None:
            continue
        packs.append(
            InspectionPack(
                key=str(template["key"]),
                title=str(template["title"]),
                job=job,
                description=str(template["description"]),
                metric_ids=[spec.id for spec in specs],
                range_hours=float(template["range_hours"]),
                step_seconds=int(template["step_seconds"]),
                current_window=str(template["current_window"]),
            )
        )
    return packs


def select_packs(
    available_jobs: Sequence[str],
    requested_jobs: Optional[Sequence[str]] = None,
    catalog: Mapping[str, Sequence[MetricSpec]] | None = None,
) -> List[InspectionPack]:
    available = {normalize_job(job) for job in available_jobs if normalize_job(job)}
    supported = {pack.job: pack for pack in build_default_packs(catalog)}
    chosen: List[InspectionPack] = []

    if requested_jobs:
        for job in requested_jobs:
            normalized = normalize_job(job)
            pack = supported.get(normalized)
            if pack is not None:
                chosen.append(pack)
        return chosen

    for job in JOB_ORDER:
        if job in available and job in supported:
            chosen.append(supported[job])
    return chosen


def unsupported_requested_jobs(requested_jobs: Sequence[str], catalog: Mapping[str, Sequence[MetricSpec]] | None = None) -> List[str]:
    supported = {pack.job for pack in build_default_packs(catalog)}
    return [job for job in requested_jobs if normalize_job(job) not in supported]


def catalog_summary(catalog: Mapping[str, Sequence[MetricSpec]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        job: [
            {
                "id": spec.id,
                "name": spec.name,
                "unit": spec.unit,
                "value_type": spec.value_type,
                "warning": spec.warning,
                "critical": spec.critical,
            }
            for spec in specs
        ]
        for job, specs in catalog.items()
    }


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
        current_window=str(item.get("current_window")) if item.get("current_window") not in {None, ""} else None,
        range_hours=_optional_float(item.get("range_hours")),
        step_seconds=_optional_int(item.get("step_seconds")),
    )


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)
