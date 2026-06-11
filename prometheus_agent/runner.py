"""End-to-end Prometheus inspection runner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

from .analysis import analysis_error_item, analyze_item
from .config import ConfigInput, load_config
from .models import InspectionResult, to_plain
from .prometheus import PrometheusClient, PrometheusError
from .report import generate_html_report


def run_inspection(
    config: ConfigInput,
    output_path: Optional[str] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """Query Prometheus, analyze risk, and generate an HTML report.

    The return value is JSON-friendly so an AI platform tool can pass it to
    later workflow steps.
    """
    cfg = load_config(config)
    inspection = cfg["inspection"]
    end_dt = _parse_end(end) if end is not None else datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=float(inspection["range_hours"]))
    client = PrometheusClient.from_config(cfg["prometheus"])

    item_results = []
    query_errors: Dict[str, str] = {}
    for item in cfg["items"]:
        item_id = str(item["id"])
        try:
            series = client.query_range(
                query=str(item["promql"]),
                start=start_dt,
                end=end_dt,
                step=int(inspection["step_seconds"]),
            )
            item_results.append(
                analyze_item(
                    item,
                    series,
                    forecast_hours=float(inspection["forecast_hours"]),
                    top_n_series=int(inspection["top_n_series"]),
                    min_points=int(inspection["min_points"]),
                )
            )
        except PrometheusError as exc:
            message = str(exc)
            query_errors[item_id] = message
            item_results.append(analysis_error_item(item, message))

    result = InspectionResult(
        generated_at=datetime.now(timezone.utc),
        start=start_dt,
        end=end_dt,
        range_hours=float(inspection["range_hours"]),
        forecast_hours=float(inspection["forecast_hours"]),
        items=item_results,
        metadata={
            "prometheus_base_url": cfg["prometheus"]["base_url"],
            "query_errors": query_errors,
        },
    )
    html = generate_html_report(result, output_path=output_path)
    return {
        "result": to_plain(result),
        "report_path": output_path,
        "html": None if output_path else html,
    }


def _parse_end(value: Union[str, datetime]) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
