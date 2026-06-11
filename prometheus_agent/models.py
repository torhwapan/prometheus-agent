"""Shared data models for the Prometheus inspection agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional


SEVERITY_ORDER = {
    "ok": 0,
    "info": 1,
    "unknown": 2,
    "warning": 3,
    "critical": 4,
}


def max_severity(values: Iterable[str]) -> str:
    severities = list(values)
    if not severities:
        return "unknown"
    return max(severities, key=lambda item: SEVERITY_ORDER.get(item, -1))


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def isoformat(value: datetime) -> str:
    return to_utc(value).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class DataPoint:
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class TimeSeries:
    labels: Dict[str, str]
    points: List[DataPoint]

    def display_name(self) -> str:
        preferred = [
            "instance",
            "pod",
            "container",
            "job",
            "namespace",
            "mountpoint",
            "device",
        ]
        parts = []
        for key in preferred:
            value = self.labels.get(key)
            if value:
                parts.append(f"{key}={value}")
        if parts:
            return ", ".join(parts[:4])
        if not self.labels:
            return "series"
        return ", ".join(f"{key}={value}" for key, value in sorted(self.labels.items())[:4])


@dataclass(frozen=True)
class SeriesAnalysis:
    labels: Dict[str, str]
    display_name: str
    severity: str
    status: str
    reason: str
    current: Optional[float]
    average: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]
    p95: Optional[float]
    slope_per_hour: Optional[float]
    forecast: Optional[float]
    time_to_warning_hours: Optional[float]
    time_to_critical_hours: Optional[float]
    point_count: int


@dataclass(frozen=True)
class ItemAnalysis:
    id: str
    name: str
    description: str
    promql: str
    unit: str
    severity: str
    status: str
    summary: str
    checked_series: int
    returned_series: int
    series: List[SeriesAnalysis] = field(default_factory=list)


@dataclass(frozen=True)
class InspectionResult:
    generated_at: datetime
    start: datetime
    end: datetime
    range_hours: float
    forecast_hours: float
    items: List[ItemAnalysis]
    metadata: Dict[str, Any] = field(default_factory=dict)


def to_plain(value: Any) -> Any:
    """Convert dataclasses and datetimes to JSON-friendly values."""
    if isinstance(value, datetime):
        return isoformat(value)
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [to_plain(item) for item in value]
    return value
