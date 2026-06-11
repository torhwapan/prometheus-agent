"""Grafana threshold discovery helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GrafanaError(RuntimeError):
    """Raised when Grafana API access fails."""


class GrafanaClient:
    """Small Grafana HTTP client based on the Python standard library."""

    def __init__(
        self,
        base_url: str,
        headers: Optional[Mapping[str, str]] = None,
        timeout_seconds: float = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Accept": "application/json", **dict(headers or {})}
        self.timeout_seconds = timeout_seconds

    def list_alert_rules(self) -> List[Mapping[str, Any]]:
        """Return Grafana managed alert rules.

        The provisioning endpoint is used first. A legacy alert endpoint is
        attempted as a fallback for older installations.
        """
        errors: List[str] = []
        for path in ("/api/v1/provisioning/alert-rules", "/api/alerts"):
            try:
                payload = self._get(path)
            except GrafanaError as exc:
                errors.append(str(exc))
                continue
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, Mapping)]
            if isinstance(payload, Mapping) and isinstance(payload.get("rules"), list):
                return [item for item in payload["rules"] if isinstance(item, Mapping)]
        raise GrafanaError("; ".join(errors) or "No Grafana alert rules endpoint returned data")

    def _get(self, path: str) -> Any:
        request = Request(f"{self.base_url}{path}", headers=self.headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise GrafanaError(f"Grafana HTTP {exc.code}: {details}") from exc
        except (URLError, TimeoutError) as exc:
            raise GrafanaError(f"Grafana connection failed: {exc}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GrafanaError(f"Grafana returned non-JSON response: {raw[:200]}") from exc


def query_grafana_thresholds(
    grafana: Mapping[str, Any],
    metric_ids: Optional[Sequence[str]] = None,
    timeout_seconds: float = 20,
) -> Dict[str, Any]:
    """Query Grafana alert rules and extract threshold hints."""
    base_url = grafana.get("base_url")
    if not base_url:
        return {"ok": False, "error": "grafana_not_configured", "thresholds": []}
    client = GrafanaClient(
        base_url=str(base_url),
        headers=grafana.get("headers") if isinstance(grafana.get("headers"), Mapping) else None,
        timeout_seconds=timeout_seconds,
    )
    try:
        rules = client.list_alert_rules()
    except GrafanaError as exc:
        return {"ok": False, "error": "grafana_query_failed", "message": str(exc), "thresholds": []}
    thresholds = extract_thresholds_from_rules(rules, metric_ids=metric_ids)
    return {"ok": True, "thresholds": thresholds, "rule_count": len(rules)}


def extract_thresholds_from_rules(
    rules: Sequence[Mapping[str, Any]],
    metric_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    wanted = {item.lower() for item in (metric_ids or [])}
    thresholds = []
    for rule in rules:
        title = str(rule.get("title") or rule.get("name") or "")
        labels = rule.get("labels") if isinstance(rule.get("labels"), Mapping) else {}
        metric_id = str(labels.get("metric_id") or labels.get("metric") or "")
        searchable = " ".join([title, metric_id]).lower()
        if wanted and not any(item in searchable for item in wanted):
            continue
        extracted = _extract_rule_thresholds(rule)
        for threshold in extracted:
            severity = str(labels.get("severity") or threshold.get("severity") or "critical")
            threshold.update(
                {
                    "rule_uid": rule.get("uid") or rule.get("id"),
                    "rule_title": title,
                    "metric_id": metric_id or _matched_metric_id(searchable, wanted),
                    "severity": severity,
                    "source": "grafana_alert_rule",
                }
            )
            thresholds.append(threshold)
    return thresholds


def merge_thresholds(
    metric_specs: Sequence[Mapping[str, Any]],
    thresholds: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge Grafana thresholds into metric specs when a rule can be matched."""
    merged = []
    for spec in metric_specs:
        item = dict(spec)
        match = _find_threshold_match(item, thresholds)
        if match:
            value = match.get("value")
            if value is not None:
                if str(match.get("severity", "critical")).lower() in {"warning", "warn"}:
                    item["warning"] = value
                else:
                    item["critical"] = value
                item["threshold_source"] = "grafana_alert_rule"
                item["grafana_rule_title"] = match.get("rule_title")
                comparator = str(match.get("comparator") or "")
                if comparator in {"lt", "lte"}:
                    item["direction"] = "lower_is_bad"
                elif comparator in {"gt", "gte"}:
                    item["direction"] = "higher_is_bad"
        merged.append(item)
    return merged


def _extract_rule_thresholds(rule: Mapping[str, Any]) -> List[Dict[str, Any]]:
    thresholds: List[Dict[str, Any]] = []
    for node in _walk(rule):
        if not isinstance(node, Mapping):
            continue
        evaluator = node.get("evaluator")
        if isinstance(evaluator, Mapping):
            comparator = str(evaluator.get("type") or "")
            params = evaluator.get("params")
            value = _first_number(params)
            if comparator and value is not None:
                thresholds.append({"comparator": comparator, "value": value})
        if str(node.get("type") or "") in {"gt", "gte", "lt", "lte"}:
            value = _first_number(node.get("params"))
            if value is not None:
                thresholds.append({"comparator": str(node["type"]), "value": value})
        if str(node.get("reducer") or "") and node.get("threshold") is not None:
            value = _number_or_none(node.get("threshold"))
            if value is not None:
                thresholds.append({"comparator": str(node.get("op") or "gt"), "value": value})
    return _dedupe_thresholds(thresholds)


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _first_number(value: Any) -> Optional[float]:
    if isinstance(value, list):
        for item in value:
            number = _number_or_none(item)
            if number is not None:
                return number
    return _number_or_none(value)


def _number_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe_thresholds(thresholds: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for threshold in thresholds:
        key = (threshold.get("comparator"), threshold.get("value"))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(threshold))
    return result


def _find_threshold_match(
    spec: Mapping[str, Any],
    thresholds: Sequence[Mapping[str, Any]],
) -> Optional[Mapping[str, Any]]:
    spec_id = str(spec.get("id") or "").lower()
    spec_name = str(spec.get("name") or "").lower()
    for threshold in thresholds:
        metric_id = str(threshold.get("metric_id") or "").lower()
        title = str(threshold.get("rule_title") or "").lower()
        if metric_id and metric_id == spec_id:
            return threshold
        if spec_id and spec_id in title:
            return threshold
        if spec_name and spec_name in title:
            return threshold
    return None


def _matched_metric_id(searchable: str, wanted: Sequence[str]) -> str:
    for metric_id in wanted:
        if metric_id in searchable:
            return metric_id
    return ""
