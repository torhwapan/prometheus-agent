"""Prometheus HTTP API client for V6."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import DataPoint, TimeSeries, to_utc

Timestamp = Union[datetime, int, float, str]


class PrometheusApiError(RuntimeError):
    """Raised when Prometheus returns an API or transport error."""


class PrometheusClient:
    def __init__(
        self,
        base_url: str,
        headers: Optional[Mapping[str, str]] = None,
        timeout_seconds: float = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            **dict(headers or {}),
        }
        self.timeout_seconds = timeout_seconds

    def api_get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        payload = self._request("GET", path, params=params)
        return payload.get("data")

    def api_post(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        payload = self._request("POST", path, params=params)
        return payload.get("data")

    def query(self, promql: str, time: Optional[Timestamp] = None) -> List[TimeSeries]:
        params: Dict[str, str] = {"query": promql}
        if time is not None:
            params["time"] = _timestamp(time)
        payload = self._request("POST", "/api/v1/query", params=params)
        result = payload.get("data", {}).get("result", [])
        return _parse_vector(result)

    def query_range(
        self,
        promql: str,
        start: Timestamp,
        end: Timestamp,
        step_seconds: int,
    ) -> List[TimeSeries]:
        payload = self._request(
            "POST",
            "/api/v1/query_range",
            params={
                "query": promql,
                "start": _timestamp(start),
                "end": _timestamp(end),
                "step": str(step_seconds),
            },
        )
        result = payload.get("data", {}).get("result", [])
        return _parse_matrix(result)

    def _request(self, method: str, path: str, params: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        if method.upper() == "GET":
            if params:
                url = f"{url}?{urlencode(params, doseq=True)}"
        else:
            data = urlencode(params or {}, doseq=True).encode("utf-8")

        request = Request(url, data=data, headers=self.headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise PrometheusApiError(f"Prometheus HTTP {exc.code}: {details}") from exc
        except (URLError, TimeoutError) as exc:
            raise PrometheusApiError(f"Prometheus connection failed: {exc}") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PrometheusApiError(f"Prometheus returned non-JSON response: {raw[:200]}") from exc
        if payload.get("status") != "success":
            raise PrometheusApiError(str(payload.get("error") or "Prometheus query failed"))
        return payload


def _timestamp(value: Timestamp) -> str:
    if isinstance(value, datetime):
        return str(to_utc(value).timestamp())
    return str(value)


def _parse_vector(result: Any) -> List[TimeSeries]:
    if not isinstance(result, list):
        return []
    series_list: List[TimeSeries] = []
    for item in result:
        if not isinstance(item, Mapping):
            continue
        point = _parse_value(item.get("value"))
        series_list.append(TimeSeries(labels=_labels(item.get("metric")), points=[] if point is None else [point]))
    return series_list


def _parse_matrix(result: Any) -> List[TimeSeries]:
    if not isinstance(result, list):
        return []
    series_list: List[TimeSeries] = []
    for item in result:
        if not isinstance(item, Mapping):
            continue
        points = [_parse_value(raw_point) for raw_point in item.get("values", [])]
        series_list.append(
            TimeSeries(
                labels=_labels(item.get("metric")),
                points=[point for point in points if point is not None],
            )
        )
    return series_list


def _parse_value(raw: Any) -> Optional[DataPoint]:
    if not isinstance(raw, list) or len(raw) != 2:
        return None
    try:
        value = float(raw[1])
        timestamp = datetime.fromtimestamp(float(raw[0]), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    if not math.isfinite(value):
        return None
    return DataPoint(timestamp=timestamp, value=value)


def _labels(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): str(value) for key, value in raw.items()}
