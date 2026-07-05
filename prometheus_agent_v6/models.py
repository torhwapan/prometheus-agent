"""Core data models for Prometheus inspection V6."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional


SEVERITY_ORDER = {
    "ok": 0,
    "info": 1,
    "warning": 2,
    "critical": 3,
    "unknown": 4,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def isoformat(value: datetime) -> str:
    return to_utc(value).isoformat().replace("+00:00", "Z")


def max_severity(values: List[str]) -> str:
    if not values:
        return "unknown"
    return max(values, key=lambda item: SEVERITY_ORDER.get(item, -1))


@dataclass(frozen=True)
class DataPoint:
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class TimeSeries:
    labels: Dict[str, str]
    points: List[DataPoint]


@dataclass(frozen=True)
class MetricSpec:
    job: str
    id: str
    name: str
    description: str
    current_promql: str
    range_promql: str
    value_type: str = "number"
    unit: str = ""
    direction: str = "higher_is_bad"
    analysis_methods: List[str] = field(default_factory=list)
    warning: Optional[float] = None
    critical: Optional[float] = None
    max_value: Optional[float] = None
    labels_to_keep: List[str] = field(default_factory=list)
    current_window: Optional[str] = None
    range_hours: Optional[float] = None
    step_seconds: Optional[int] = None


@dataclass(frozen=True)
class InspectionPack:
    key: str
    title: str
    job: str
    description: str
    metric_ids: List[str]
    range_hours: float
    step_seconds: int
    current_window: str = "5m"


@dataclass(frozen=True)
class QueryTask:
    task_id: str
    pack_key: str
    pack_title: str
    job: str
    metric_id: str
    metric_name: str
    instance: Optional[str]
    current_promql: str
    range_promql: str
    start: datetime
    end: datetime
    step_seconds: int
    spec: MetricSpec


def to_plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return isoformat(value)
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [to_plain(item) for item in value]
    return value
