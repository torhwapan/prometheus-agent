"""Prometheus HTTP API client for v2 service."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import DataPoint, to_utc

Timestamp = Union[datetime, int, float, str]


class PrometheusQueryError(RuntimeError):
    pass


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

    def query(self, promql: str, time: Optional[Timestamp] = None) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {"query": promql}
        if time is not None:
            params["time"] = _timestamp(time)
        payload = self._post("/api/v1/query", params)
        result = payload.get("data", {}).get("result", [])
        if not isinstance(result, list):
            return []
        parsed = []
        for item in result:
            if not isinstance(item, Mapping):
                continue
            point = _parse_value(item.get("value"))
            parsed.append(
                {
                    "labels": _labels(item.get("metric")),
                    "points": [] if point is None else [point],
                }
            )
        return parsed

    def query_range(
        self,
        promql: str,
        start: Timestamp,
        end: Timestamp,
        step_seconds: int,
    ) -> List[Dict[str, Any]]:
        payload = self._post(
            "/api/v1/query_range",
            {
                "query": promql,
                "start": _timestamp(start),
                "end": _timestamp(end),
                "step": str(step_seconds),
            },
        )
        result = payload.get("data", {}).get("result", [])
        if not isinstance(result, list):
            return []
        parsed = []
        for item in result:
            if not isinstance(item, Mapping):
                continue
            points = [_parse_value(value) for value in item.get("values", [])]
            parsed.append(
                {
                    "labels": _labels(item.get("metric")),
                    "points": [point for point in points if point is not None],
                }
            )
        return parsed

    def _post(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=urlencode(params).encode("utf-8"),
            headers=self.headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise PrometheusQueryError(f"Prometheus HTTP {exc.code}: {details}") from exc
        except (URLError, TimeoutError) as exc:
            raise PrometheusQueryError(f"Prometheus connection failed: {exc}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PrometheusQueryError(f"Prometheus returned non-JSON response: {raw[:200]}") from exc
        if payload.get("status") != "success":
            raise PrometheusQueryError(str(payload.get("error") or "Prometheus query failed"))
        return payload


def _timestamp(value: Timestamp) -> str:
    if isinstance(value, datetime):
        return str(to_utc(value).timestamp())
    return str(value)


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
