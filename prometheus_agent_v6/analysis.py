"""Deterministic fixed-rule analysis for V6."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .models import DataPoint, MetricSpec, SEVERITY_ORDER, TimeSeries, max_severity


def analyze_query_results(query_results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    for result in query_results:
        findings.extend(_analyze_task_result(result))

    findings.sort(key=_sort_key, reverse=True)
    risky = [item for item in findings if item["severity"] != "ok"]
    return {
        "severity": max_severity([item["severity"] for item in findings]),
        "counts": _counts(findings),
        "findings": findings,
        "risky_findings": risky,
    }


def _analyze_task_result(result: Mapping[str, Any]) -> List[Dict[str, Any]]:
    task = result["task"]
    spec: MetricSpec = task.spec
    current_series = result.get("current", [])
    range_series = result.get("range", [])
    errors = result.get("errors", [])

    current_by_key = {_series_key(series.labels): _last_value(series.points) for series in current_series}
    findings: List[Dict[str, Any]] = []

    if range_series:
        for series in range_series:
            current_value = current_by_key.get(_series_key(series.labels))
            if current_value is None:
                current_value = _last_value(series.points)
            analysis = _analyze_series(series.points, current_value, spec)
            findings.append(
                _make_finding(
                    task=task,
                    labels=series.labels,
                    current_value=current_value,
                    severity=analysis["severity"],
                    reason=analysis["reason"],
                    analysis=analysis,
                )
            )
        return findings

    if current_series:
        for series in current_series:
            current_value = _last_value(series.points)
            severity = _threshold_severity(current_value, spec)
            reason = _fallback_reason(severity, errors)
            findings.append(
                _make_finding(
                    task=task,
                    labels=series.labels,
                    current_value=current_value,
                    severity=severity,
                    reason=reason,
                    analysis={
                        "current": current_value,
                        "warning": spec.warning,
                        "critical": spec.critical,
                        "max_value": spec.max_value,
                        "unit": spec.unit,
                        "fallback_current_only": True,
                    },
                )
            )
        return findings

    return [
        _make_finding(
            task=task,
            labels={},
            current_value=None,
            severity="unknown",
            reason=_errors_text(errors) or "当前任务未返回任何时间序列数据。",
            analysis={"unit": spec.unit},
        )
    ]


def _make_finding(
    *,
    task: Any,
    labels: Mapping[str, str],
    current_value: Optional[float],
    severity: str,
    reason: str,
    analysis: Mapping[str, Any],
) -> Dict[str, Any]:
    key = "|".join(
        [
            str(task.job),
            str(labels.get("instance") or task.instance or ""),
            str(task.metric_id),
            _labels_signature(labels),
        ]
    )
    return {
        "finding_key": key,
        "pack_key": task.pack_key,
        "pack_title": task.pack_title,
        "job": task.job,
        "instance": labels.get("instance") or task.instance,
        "metric_id": task.metric_id,
        "metric_name": task.metric_name,
        "severity": severity,
        "reason": reason,
        "current_value": current_value,
        "labels": dict(labels),
        "analysis": dict(analysis),
        "ai_comment": None,
    }


def _analyze_series(points: Sequence[DataPoint], current_value: Optional[float], spec: MetricSpec) -> Dict[str, Any]:
    values = [point.value for point in points if math.isfinite(point.value)]
    if len(values) < 4:
        return {
            "severity": "unknown",
            "reason": f"有效采样点不足，当前仅有 {len(values)} 个点，无法稳定判断趋势。",
            "point_count": len(values),
            "unit": spec.unit,
        }

    current = current_value if current_value is not None else values[-1]
    minimum = min(values)
    maximum = max(values)
    average = sum(values) / len(values)
    p95 = _percentile(values, 95)
    slope_per_hour = _slope_per_hour(points)
    forecast_24h = current + slope_per_hour * 24
    threshold_severity = _threshold_severity(current, spec)
    forecast_severity = _threshold_severity(forecast_24h, spec)
    burst = "burst" in spec.analysis_methods and _burst_detected(values, spec)
    sustained_bad = "sustained_growth" in spec.analysis_methods and _sustained_deterioration(values, spec)
    time_to_limit = "time_to_limit" in spec.analysis_methods and _time_to_limit(current, slope_per_hour, spec)

    severity = max_severity([threshold_severity, forecast_severity])
    reasons: List[str] = []

    if threshold_severity in {"warning", "critical"}:
        reasons.append(_threshold_reason(current, threshold_severity, spec))
    if forecast_severity in {"warning", "critical"} and forecast_severity != threshold_severity:
        reasons.append(f"按当前趋势推算，24 小时内可能触达{_severity_cn(forecast_severity)}阈值。")
    if burst:
        severity = _raise_to_at_least(severity, "warning")
        reasons.append("最近一段时间波动幅度明显放大，存在突增或突降风险。")
    if sustained_bad:
        severity = _raise_to_at_least(severity, "info")
        reasons.append(_trend_reason(spec))
    if isinstance(time_to_limit, float) and time_to_limit <= 24:
        severity = _raise_to_at_least(severity, "warning")
        reasons.append(f"按当前变化速度，预计约 {time_to_limit:.1f} 小时后触达限制值。")
    if not reasons:
        reasons.append("当前未发现明显超阈值、趋势恶化或波动异常。")

    return {
        "severity": severity,
        "reason": " ".join(reasons),
        "point_count": len(values),
        "current": current,
        "min": minimum,
        "max": maximum,
        "avg": average,
        "p95": p95,
        "slope_per_hour": slope_per_hour,
        "forecast_24h": forecast_24h,
        "burst": burst,
        "sustained_deterioration": sustained_bad,
        "time_to_limit_hours": time_to_limit if isinstance(time_to_limit, float) else None,
        "warning": spec.warning,
        "critical": spec.critical,
        "max_value": spec.max_value,
        "unit": spec.unit,
    }


def _threshold_reason(value: float, severity: str, spec: MetricSpec) -> str:
    if spec.direction == "lower_is_bad":
        return f"当前值 {value:.3f}{spec.unit} 已低于{_severity_cn(severity)}阈值。"
    return f"当前值 {value:.3f}{spec.unit} 已达到{_severity_cn(severity)}阈值。"


def _trend_reason(spec: MetricSpec) -> str:
    if spec.direction == "lower_is_bad":
        return "采样序列整体持续下滑，且未见明显修复迹象。"
    return "采样序列整体持续抬升，且未见明显回落迹象。"


def _fallback_reason(severity: str, errors: Sequence[Mapping[str, Any]]) -> str:
    base = _errors_text(errors) or "范围查询失败，已退化为当前值判定。"
    if severity in {"warning", "critical"}:
        return f"{base} 当前值已达到告警阈值。"
    if severity == "ok":
        return f"{base} 当前值暂未达到告警阈值。"
    return f"{base} 当前值不可用或不足以判断。"


def _errors_text(errors: Sequence[Mapping[str, Any]]) -> str:
    messages = [str(item.get("message") or "").strip() for item in errors if isinstance(item, Mapping)]
    messages = [message for message in messages if message]
    return "; ".join(messages)


def _threshold_severity(value: Optional[float], spec: MetricSpec) -> str:
    if value is None:
        return "unknown"
    if spec.direction == "lower_is_bad":
        if spec.critical is not None and value <= float(spec.critical):
            return "critical"
        if spec.warning is not None and value <= float(spec.warning):
            return "warning"
        return "ok"
    if spec.critical is not None and value >= float(spec.critical):
        return "critical"
    if spec.warning is not None and value >= float(spec.warning):
        return "warning"
    return "ok"


def _burst_detected(values: Sequence[float], spec: MetricSpec) -> bool:
    if len(values) < 8:
        return False
    midpoint = max(1, len(values) // 2)
    early = values[:midpoint]
    late = values[midpoint:]
    early_avg = sum(early) / len(early)
    late_avg = sum(late) / len(late)
    if abs(early_avg) < 1e-9:
        return abs(late_avg) > 0
    change_ratio = abs(late_avg - early_avg) / abs(early_avg)
    if spec.direction == "lower_is_bad":
        return change_ratio >= 0.5 and late_avg < early_avg
    return change_ratio >= 0.5 and late_avg > early_avg


def _sustained_deterioration(values: Sequence[float], spec: MetricSpec) -> bool:
    if len(values) < 6:
        return False
    bad_steps = 0
    total = 0
    for before, after in zip(values, values[1:]):
        total += 1
        if spec.direction == "lower_is_bad":
            if after <= before:
                bad_steps += 1
        else:
            if after >= before:
                bad_steps += 1
    if total <= 0 or bad_steps / total < 0.8:
        return False
    if spec.direction == "lower_is_bad":
        return values[-1] < values[0]
    return values[-1] > values[0]


def _time_to_limit(current: float, slope_per_hour: float, spec: MetricSpec) -> Optional[float]:
    if spec.direction == "lower_is_bad":
        limit = spec.critical if spec.critical is not None else spec.warning
        if limit is None or slope_per_hour >= 0:
            return None
        if current <= float(limit):
            return 0.0
        hours = (float(limit) - current) / slope_per_hour
        return hours if math.isfinite(hours) and hours >= 0 else None

    limit = spec.max_value if spec.max_value is not None else spec.critical if spec.critical is not None else spec.warning
    if limit is None or slope_per_hour <= 0:
        return None
    if current >= float(limit):
        return 0.0
    hours = (float(limit) - current) / slope_per_hour
    return hours if math.isfinite(hours) and hours >= 0 else None


def _slope_per_hour(points: Sequence[DataPoint]) -> float:
    if len(points) < 2:
        return 0.0
    first = points[0].timestamp.timestamp()
    xs = [point.timestamp.timestamp() - first for point in points]
    ys = [point.value for point in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator * 3600


def _percentile(values: Sequence[float], percentile: float) -> float:
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * percentile / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _last_value(points: Sequence[DataPoint]) -> Optional[float]:
    if not points:
        return None
    return points[-1].value


def _series_key(labels: Mapping[str, Any]) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


def _raise_to_at_least(current: str, minimum: str) -> str:
    if SEVERITY_ORDER.get(current, 0) < SEVERITY_ORDER.get(minimum, 0):
        return minimum
    return current


def _severity_cn(value: str) -> str:
    mapping = {
        "critical": "高危",
        "warning": "预警",
        "info": "关注",
        "ok": "正常",
        "unknown": "未知",
    }
    return mapping.get(value, value)


def _labels_signature(labels: Mapping[str, str]) -> str:
    items = [(str(key), str(value)) for key, value in labels.items() if key != "__name__"]
    items.sort()
    return ",".join(f"{key}={value}" for key, value in items)


def _counts(items: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {"critical": 0, "warning": 0, "info": 0, "ok": 0, "unknown": 0}
    for item in items:
        severity = str(item.get("severity") or "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _sort_key(item: Mapping[str, Any]) -> Tuple[int, str, str, str, float]:
    severity = SEVERITY_ORDER.get(str(item.get("severity") or "unknown"), -1)
    current_value = item.get("current_value")
    numeric_value = abs(float(current_value)) if current_value is not None else -1.0
    return (
        severity,
        str(item.get("job") or ""),
        str(item.get("instance") or ""),
        str(item.get("metric_id") or ""),
        numeric_value,
    )
