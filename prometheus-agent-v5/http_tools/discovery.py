from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prometheus_agent_v2.prometheus import PrometheusQueryError  # noqa: E402


class PrometheusDiscoveryClient:
    def __init__(
        self,
        base_url: str,
        headers: Optional[Mapping[str, str]] = None,
        timeout_seconds: float = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            **dict(headers or {}),
        }
        self.timeout_seconds = timeout_seconds

    def job_values(self) -> Any:
        return self._get("/api/v1/label/job/values")

    def metric_names(self) -> Any:
        return self._get("/api/v1/label/__name__/values")

    def label_values(self, label: str) -> Any:
        return self._get(f"/api/v1/label/{label}/values")

    def series(self, match: str, start: Any = None, end: Any = None) -> Any:
        params: Dict[str, Any] = {"match[]": match}
        if start is not None:
            params["start"] = str(start)
        if end is not None:
            params["end"] = str(end)
        return self._get("/api/v1/series", params)

    def targets(self) -> Any:
        return self._get("/api/v1/targets")

    def alerts(self) -> Any:
        return self._get("/api/v1/alerts")

    def metadata(self, metric: str | None = None) -> Any:
        params = {"metric": metric} if metric else None
        return self._get("/api/v1/metadata", params)

    def _get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"
        request = Request(url, headers=self.headers, method="GET")
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
        return payload.get("data")
