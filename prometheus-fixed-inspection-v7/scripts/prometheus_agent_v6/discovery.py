"""Prometheus environment discovery for V6."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .catalog import normalize_job
from .prometheus import PrometheusClient


class PrometheusDiscoveryClient:
    def __init__(
        self,
        base_url: str,
        headers: Optional[Mapping[str, str]] = None,
        timeout_seconds: float = 20,
    ) -> None:
        self.client = PrometheusClient(base_url=base_url, headers=headers, timeout_seconds=timeout_seconds)

    def job_values(self) -> List[str]:
        data = self.client.api_get("/api/v1/label/job/values")
        if not isinstance(data, list):
            return []
        return [str(item) for item in data if str(item).strip()]

    def targets(self) -> Mapping[str, Any]:
        data = self.client.api_get("/api/v1/targets")
        return data if isinstance(data, Mapping) else {}

    def snapshot(self) -> Dict[str, Any]:
        raw_jobs = self.job_values()
        targets = self.targets()
        instances_by_job: Dict[str, List[str]] = {}
        active_targets = targets.get("activeTargets", []) if isinstance(targets, Mapping) else []
        if isinstance(active_targets, list):
            for target in active_targets:
                if not isinstance(target, Mapping):
                    continue
                labels = target.get("labels", {})
                discovered_labels = target.get("discoveredLabels", {})
                if not isinstance(labels, Mapping):
                    labels = {}
                if not isinstance(discovered_labels, Mapping):
                    discovered_labels = {}
                job = normalize_job(labels.get("job") or discovered_labels.get("job"))
                instance = str(labels.get("instance") or discovered_labels.get("__address__") or "").strip()
                if job and instance:
                    instances_by_job.setdefault(job, [])
                    if instance not in instances_by_job[job]:
                        instances_by_job[job].append(instance)

        normalized_jobs = sorted({normalize_job(job) for job in raw_jobs if normalize_job(job)} | set(instances_by_job.keys()))
        return {
            "raw_jobs": sorted(set(raw_jobs)),
            "normalized_jobs": normalized_jobs,
            "instances_by_job": {job: sorted(values) for job, values in sorted(instances_by_job.items())},
            "active_target_count": len(active_targets) if isinstance(active_targets, list) else 0,
        }
