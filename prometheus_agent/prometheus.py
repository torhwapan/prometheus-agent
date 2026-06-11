"""Prometheus HTTP API client."""

from __future__ import annotations

import base64
import json
import math
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import DataPoint, TimeSeries, to_utc

Timestamp = Union[datetime, int, float, str]


class PrometheusError(RuntimeError):
    """Raised when Prometheus returns an API or transport error."""


class PrometheusClient:
    """Small Prometheus API client based on the Python standard library."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 20,
        headers: Optional[Mapping[str, str]] = None,
        basic_auth: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.headers = dict(headers or {})
        self.basic_auth = dict(basic_auth or {})

    @classmethod
    def from_config(cls, config: Mapping[str, object]) -> "PrometheusClient":
        return cls(
            base_url=str(config["base_url"]),
            timeout_seconds=float(config.get("timeout_seconds", 20)),
            headers=config.get("headers") if isinstance(config.get("headers"), Mapping) else None,
            basic_auth=(
                config.get("basic_auth")
                if isinstance(config.get("basic_auth"), Mapping)
                else None
            ),
        )

    def query_range(
        self,
        query: str,
        start: Timestamp,
        end: Timestamp,
        step: Union[int, float, str],
    ) -> List[TimeSeries]:
        """Run /api/v1/query_range and return matrix series."""
        payload = self._post(
            "/api/v1/query_range",
            {
                "query": query,
                "start": _format_timestamp(start),
                "end": _format_timestamp(end),
                "step": str(step),
            },
        )
        data = payload.get("data", {})
        result_type = data.get("resultType")
        if result_type != "matrix":
            raise PrometheusError(f"Expected matrix result, got {result_type!r}")
        return [_parse_matrix_series(item) for item in data.get("result", [])]

    def query(self, query: str, time: Optional[Timestamp] = None) -> List[TimeSeries]:
        """Run /api/v1/query and normalize vector results into one-point series."""
        params: Dict[str, str] = {"query": query}
        if time is not None:
            params["time"] = _format_timestamp(time)
        payload = self._post("/api/v1/query", params)
        data = payload.get("data", {})
        result_type = data.get("resultType")
        if result_type not in {"vector", "matrix"}:
            raise PrometheusError(f"Unsupported result type {result_type!r}")
        if result_type == "matrix":
            return [_parse_matrix_series(item) for item in data.get("result", [])]
        return [_parse_vector_series(item) for item in data.get("result", [])]

    def _post(self, path: str, params: Mapping[str, str]) -> Mapping[str, object]:
        url = f"{self.base_url}{path}"
        body = urlencode(params).encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            **self.headers,
        }
        username = self.basic_auth.get("username")
        password = self.basic_auth.get("password")
        if username or password:
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"

        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise PrometheusError(f"Prometheus HTTP {exc.code}: {details}") from exc
        except URLError as exc:
            raise PrometheusError(f"Prometheus connection failed: {exc}") from exc
        except TimeoutError as exc:
            raise PrometheusError(f"Prometheus request timed out: {exc}") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PrometheusError(f"Prometheus returned non-JSON response: {raw[:200]}") from exc

        if payload.get("status") != "success":
            error_type = payload.get("errorType", "error")
            message = payload.get("error", "unknown Prometheus API error")
            raise PrometheusError(f"{error_type}: {message}")
        return payload


def query_prometheus_range(
    base_url: str,
    promql: str,
    start: Timestamp,
    end: Timestamp,
    step_seconds: int,
    headers: Optional[Mapping[str, str]] = None,
    basic_auth: Optional[Mapping[str, str]] = None,
    timeout_seconds: float = 20,
) -> List[TimeSeries]:
    """Convenience function for AI-platform tool wrappers."""
    client = PrometheusClient(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        headers=headers,
        basic_auth=basic_auth,
    )
    return client.query_range(promql, start=start, end=end, step=step_seconds)


def _format_timestamp(value: Timestamp) -> str:
    if isinstance(value, datetime):
        return str(to_utc(value).timestamp())
    return str(value)


def _parse_matrix_series(item: Mapping[str, object]) -> TimeSeries:
    labels = _string_dict(item.get("metric", {}))
    raw_values = item.get("values", [])
    points = [_parse_point(raw) for raw in _iter_values(raw_values)]
    return TimeSeries(labels=labels, points=[point for point in points if point is not None])


def _parse_vector_series(item: Mapping[str, object]) -> TimeSeries:
    labels = _string_dict(item.get("metric", {}))
    point = _parse_point(item.get("value"))
    return TimeSeries(labels=labels, points=[] if point is None else [point])


def _iter_values(value: object) -> Iterable[object]:
    if isinstance(value, list):
        return value
    return []


def _parse_point(raw: object) -> Optional[DataPoint]:
    if not isinstance(raw, list) or len(raw) != 2:
        return None
    try:
        timestamp = datetime.fromtimestamp(float(raw[0]), tz=timezone.utc)
        metric_value = float(raw[1])
    except (TypeError, ValueError, OSError):
        return None
    if not math.isfinite(metric_value):
        return None
    return DataPoint(timestamp=timestamp, value=metric_value)


def _string_dict(value: object) -> Dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}
