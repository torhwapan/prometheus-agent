"""Resolve user target hints to approved Prometheus targets."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union
from urllib.parse import urlparse


TargetConfigInput = Union[str, Path, Mapping[str, Any]]


def resolve_target(
    target_hint: str,
    domain: Optional[str] = None,
    env: Optional[str] = None,
    instance_hint: Optional[str] = None,
    targets_config: TargetConfigInput = "configs/targets.example.json",
) -> Dict[str, Any]:
    """Resolve a natural-language target hint to one allowed Prometheus target."""
    targets = _load_targets(targets_config)
    matches = _find_matches(targets, target_hint=target_hint, env=env)
    if not matches:
        return {
            "ok": False,
            "error": "target_not_found",
            "message": f"No configured Prometheus target matched {target_hint!r}.",
            "candidates": _candidate_summary(targets),
        }
    if len(matches) > 1:
        return {
            "ok": False,
            "error": "ambiguous_target",
            "message": f"Multiple Prometheus targets matched {target_hint!r}.",
            "candidates": _candidate_summary(matches),
        }

    target = matches[0]
    domain_scope = _domain_scope(target, domain)
    warnings: List[str] = []
    if domain and domain_scope is None:
        warnings.append(f"Target {target.get('id')} has no domain scope for {domain!r}.")
        domain_scope = {"job_patterns": []}

    defaults = target.get("defaults") if isinstance(target.get("defaults"), Mapping) else {}
    resolved = {
        "ok": True,
        "target": {
            "id": target.get("id"),
            "name": target.get("name"),
            "env": target.get("env"),
            "base_url": target.get("base_url"),
            "headers": _auth_headers(target.get("auth")),
            "grafana": _resolved_grafana(target.get("grafana")),
        },
        "query_scope": {
            "domain": domain,
            "job_patterns": list(domain_scope.get("job_patterns", [])) if domain_scope else [],
            "instance_hint": instance_hint,
            "range_hours": float(defaults.get("range_hours", 24)),
            "step_seconds": int(defaults.get("step_seconds", 60)),
            "forecast_hours": float(defaults.get("forecast_hours", 24)),
        },
        "warnings": warnings,
    }
    return resolved


def list_targets(targets_config: TargetConfigInput = "configs/targets.example.json") -> Dict[str, Any]:
    targets = _load_targets(targets_config)
    return {"ok": True, "targets": _candidate_summary(targets)}


def _load_targets(config: TargetConfigInput) -> List[Mapping[str, Any]]:
    if isinstance(config, Mapping):
        raw = dict(config)
    else:
        with Path(config).open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    targets = raw.get("targets")
    if not isinstance(targets, list):
        raise ValueError("targets config must contain a targets list")
    return [target for target in targets if isinstance(target, Mapping)]


def _find_matches(
    targets: Sequence[Mapping[str, Any]],
    target_hint: str,
    env: Optional[str],
) -> List[Mapping[str, Any]]:
    hint = _normalize(target_hint)
    matches = []
    for target in targets:
        if env and _normalize(str(target.get("env", ""))) != _normalize(env):
            continue
        searchable = _target_search_terms(target)
        if hint in searchable:
            matches.append(target)
            continue
        if any(hint and hint in term for term in searchable):
            matches.append(target)
    return matches


def _target_search_terms(target: Mapping[str, Any]) -> List[str]:
    terms = [
        str(target.get("id", "")),
        str(target.get("name", "")),
        str(target.get("env", "")),
        str(target.get("base_url", "")),
    ]
    aliases = target.get("aliases", [])
    if isinstance(aliases, list):
        terms.extend(str(alias) for alias in aliases)
    parsed = urlparse(str(target.get("base_url", "")))
    if parsed.hostname:
        terms.append(parsed.hostname)
    return [_normalize(term) for term in terms if term]


def _domain_scope(target: Mapping[str, Any], domain: Optional[str]) -> Optional[Mapping[str, Any]]:
    if not domain:
        return {"job_patterns": []}
    domains = target.get("domains")
    if not isinstance(domains, Mapping):
        return None
    scope = domains.get(domain)
    if not isinstance(scope, Mapping):
        return None
    return scope


def _auth_headers(auth: object) -> Dict[str, str]:
    if not isinstance(auth, Mapping):
        return {}
    auth_type = str(auth.get("type") or "none")
    if auth_type == "none":
        return {}
    if auth_type == "bearer":
        token = _secret_value(auth.get("token"), auth.get("token_env"))
        return {"Authorization": f"Bearer {token}"} if token else {}
    if auth_type == "basic":
        username = _secret_value(auth.get("username"), auth.get("username_env"))
        password = _secret_value(auth.get("password"), auth.get("password_env"))
        if username or password:
            import base64

            encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            return {"Authorization": f"Basic {encoded}"}
    if auth_type == "header":
        name = str(auth.get("header_name") or "")
        value = _secret_value(auth.get("header_value"), auth.get("header_value_env"))
        if name and value:
            return {name: value}
    return {}


def _resolved_grafana(grafana: object) -> Optional[Dict[str, Any]]:
    if not isinstance(grafana, Mapping):
        return None
    return {
        "base_url": grafana.get("base_url"),
        "datasource_uid": grafana.get("datasource_uid"),
        "headers": _auth_headers(grafana.get("auth")),
    }


def _secret_value(value: object, env_name: object) -> str:
    if env_name:
        return os.environ.get(str(env_name), "")
    return "" if value is None else str(value)


def _candidate_summary(targets: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": target.get("id"),
            "name": target.get("name"),
            "env": target.get("env"),
            "base_url": target.get("base_url"),
        }
        for target in targets
    ]


def _normalize(value: str) -> str:
    return value.strip().lower().rstrip("/")
