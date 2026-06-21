from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class SemanticSpec:
    key: str
    mode: str
    job: str
    metric_ids: List[str]
    default_range_hours: float
    default_step_seconds: int = 60
    default_current_window: str = "5m"
    default_comparison: Optional[str] = None
    default_threshold: Optional[float] = None
    default_top_n: Optional[int] = None
    value_source: str = "current"
    order: str = "desc"
    description: str = ""


SEMANTIC_SPECS: Dict[str, SemanticSpec] = {
    "redis-health": SemanticSpec(
        key="redis-health",
        mode="inspection",
        job="redis_exporter",
        metric_ids=[
            "redis_up",
            "redis_memory_usage",
            "redis_connected_clients",
            "redis_blocked_clients",
            "redis_mem_fragmentation_ratio",
            "redis_evicted_keys_rate",
            "redis_rejected_connections_rate",
        ],
        default_range_hours=24,
        description="Inspect redis exporter metrics for availability and pressure risk.",
    ),
    "jvm-memory-risk": SemanticSpec(
        key="jvm-memory-risk",
        mode="inspection",
        job="java_jmx",
        metric_ids=[
            "jvm_process_cpu_usage",
            "jvm_heap_usage",
            "jvm_gc_time_rate",
            "jvm_threads_live",
            "jvm_fd_usage",
        ],
        default_range_hours=24,
        description="Inspect JVM memory and process pressure risk.",
    ),
    "rabbitmq-consumer-capacity": SemanticSpec(
        key="rabbitmq-consumer-capacity",
        mode="metric_filter",
        job="rabbitmq_exporter",
        metric_ids=["rabbitmq_queue_consumer_utilisation"],
        default_range_hours=24,
        default_comparison="<",
        default_threshold=70.0,
        value_source="avg",
        order="asc",
        description="Find queues whose consumer utilisation is low over a recent window.",
    ),
    "node-memory-usage": SemanticSpec(
        key="node-memory-usage",
        mode="metric_filter",
        job="node_exporter",
        metric_ids=["node_memory_usage"],
        default_range_hours=1,
        default_comparison=">",
        default_threshold=70.0,
        value_source="current",
        order="desc",
        description="Find hosts whose memory usage exceeds a threshold.",
    ),
    "node-cpu-top": SemanticSpec(
        key="node-cpu-top",
        mode="metric_topn",
        job="node_exporter",
        metric_ids=["node_cpu_usage"],
        default_range_hours=1,
        default_top_n=10,
        value_source="current",
        order="desc",
        description="Return top N hosts by CPU usage.",
    ),
}


def get_semantic(key: str | None) -> Optional[SemanticSpec]:
    if not key:
        return None
    return SEMANTIC_SPECS.get(str(key).strip())


def semantic_summary() -> Dict[str, Dict[str, Any]]:
    return {key: asdict(spec) for key, spec in SEMANTIC_SPECS.items()}


def resolve_semantic_payload(
    payload: Mapping[str, Any],
    expected_mode: str | None = None,
) -> Dict[str, Any]:
    semantic_key = str(payload.get("semantic_key") or payload.get("semantic_hint") or "").strip()
    spec = get_semantic(semantic_key)
    if spec is None:
        return {"ok": False, "error": "unsupported_semantic_key", "semantic_key": semantic_key}
    if expected_mode and spec.mode != expected_mode:
        return {
            "ok": False,
            "error": "semantic_mode_mismatch",
            "semantic_key": spec.key,
            "expected_mode": expected_mode,
            "actual_mode": spec.mode,
        }
    return {
        "ok": True,
        "resolved": {
            "semantic_key": spec.key,
            "mode": spec.mode,
            "job": str(payload.get("job") or spec.job),
            "instance": payload.get("instance"),
            "metric_ids": list(payload.get("metric_ids") or spec.metric_ids),
            "range_hours": float(payload.get("range_hours", spec.default_range_hours)),
            "step_seconds": int(payload.get("step_seconds", spec.default_step_seconds)),
            "current_window": str(payload.get("current_window") or spec.default_current_window),
            "comparison": payload.get("comparison", spec.default_comparison),
            "threshold": _optional_float(payload.get("threshold", spec.default_threshold)),
            "top_n": _optional_int(payload.get("top_n", spec.default_top_n)),
            "value_source": str(payload.get("value_source") or spec.value_source),
            "order": str(payload.get("order") or spec.order),
            "description": spec.description,
        },
    }


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)
