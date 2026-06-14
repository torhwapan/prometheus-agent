"""Build compact AI inputs from metric range samples."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple


def build_ai_series_inputs(
    query_results: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
    max_points_per_series: int = 24,
    risky_only: bool = False,
) -> Dict[str, Any]:
    """Build per-series payloads for AI supplemental sample analysis."""
    analysis_by_key = {
        _analysis_key(item): item
        for item in analysis.get("items", [])
        if isinstance(item, Mapping)
    }
    payloads = []
    for result in query_results:
        task = result.get("task", {})
        if not isinstance(task, Mapping):
            continue
        for series in result.get("range", []):
            if not isinstance(series, Mapping):
                continue
            labels = series.get("labels", {}) if isinstance(series.get("labels"), Mapping) else {}
            key = (
                str(task.get("job") or ""),
                str(labels.get("instance") or task.get("instance") or ""),
                str(task.get("metric_id") or ""),
            )
            item_analysis = analysis_by_key.get(key)
            severity = str(item_analysis.get("severity") if item_analysis else "unknown")
            if risky_only and severity == "ok":
                continue
            points = series.get("points", [])
            sampled_points = _sample_points(points if isinstance(points, list) else [], max_points_per_series)
            payloads.append(
                {
                    "job": task.get("job"),
                    "instance": labels.get("instance") or task.get("instance"),
                    "metric_id": task.get("metric_id"),
                    "metric_name": task.get("metric_name"),
                    "series_labels": labels,
                    "python_severity": severity,
                    "python_reason": item_analysis.get("reason") if item_analysis else None,
                    "python_analysis": item_analysis.get("analysis") if item_analysis else {},
                    "sample_policy": {
                        "original_point_count": len(points) if isinstance(points, list) else 0,
                        "included_point_count": len(sampled_points),
                        "sampling": "evenly_spaced",
                    },
                    "range_points": sampled_points,
                    "instruction": (
                        "Analyze this metric's historical samples for additional concerns that "
                        "the fixed Python rules may not capture. Do not change python_severity."
                    ),
                }
            )
    return {"ok": True, "items": payloads}


def merge_ai_series_findings(
    analysis: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Merge AI supplemental findings into deterministic analysis items."""
    finding_by_key = {
        (
            str(item.get("job") or ""),
            str(item.get("instance") or ""),
            str(item.get("metric_id") or ""),
        ): item
        for item in findings
    }
    merged = dict(analysis)
    merged_items = []
    for item in analysis.get("items", []):
        if not isinstance(item, Mapping):
            continue
        updated = dict(item)
        key = (
            str(updated.get("job") or ""),
            str(updated.get("instance") or ""),
            str(updated.get("metric_id") or ""),
        )
        finding = finding_by_key.get(key)
        if finding:
            updated["ai_sample_analysis"] = {
                "summary": finding.get("summary"),
                "extra_risks": finding.get("extra_risks", []),
                "suggestion": finding.get("suggestion"),
            }
            updated["ai_comment"] = finding.get("summary") or updated.get("ai_comment")
        merged_items.append(updated)
    merged["items"] = merged_items
    merged["risky_items"] = [item for item in merged_items if item.get("severity") != "ok"]
    return {"ok": True, "analysis": merged}


def _sample_points(points: Sequence[Mapping[str, Any]], limit: int) -> List[Mapping[str, Any]]:
    if limit <= 0 or len(points) <= limit:
        return [dict(point) for point in points if isinstance(point, Mapping)]
    if limit == 1:
        return [dict(points[-1])]
    indexes = sorted({round(i * (len(points) - 1) / (limit - 1)) for i in range(limit)})
    return [dict(points[index]) for index in indexes if isinstance(points[index], Mapping)]


def _analysis_key(item: Mapping[str, Any]) -> Tuple[str, str, str]:
    return (
        str(item.get("job") or ""),
        str(item.get("instance") or ""),
        str(item.get("metric_id") or ""),
    )
