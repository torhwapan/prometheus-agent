"""End-to-end V6 inspection orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .analysis import analyze_query_results
from .catalog import load_catalog, normalize_job, select_packs, unsupported_requested_jobs
from .discovery import PrometheusDiscoveryClient
from .llm import LlmClient, LlmError, LlmSettings
from .models import QueryTask, TimeSeries, isoformat, to_plain, utc_now
from .planner import build_plan
from .prometheus import PrometheusApiError, PrometheusClient
from .report import render_html


def inspect_prometheus(
    prometheus_url: str,
    *,
    instance: Optional[str] = None,
    jobs: Optional[Sequence[str]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout_seconds: float = 20,
    output_path: Optional[str] = None,
    llm_settings: Optional[LlmSettings] = None,
    enable_ai: bool = True,
) -> Dict[str, Any]:
    if not prometheus_url or not str(prometheus_url).strip():
        raise ValueError("prometheus_url is required")

    normalized_url = str(prometheus_url).rstrip("/")
    catalog = load_catalog()
    generated_at = utc_now()
    warnings: List[str] = []

    discovery_client = PrometheusDiscoveryClient(
        base_url=normalized_url,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    discovery = discovery_client.snapshot()

    normalized_requested_jobs = [normalize_job(job) for job in jobs or [] if normalize_job(job)]
    unsupported_jobs = unsupported_requested_jobs(jobs or [], catalog)
    if unsupported_jobs:
        warnings.append(f"以下 job 当前没有固定巡检 pack，已忽略: {', '.join(unsupported_jobs)}")

    packs = select_packs(
        discovery.get("normalized_jobs", []),
        requested_jobs=normalized_requested_jobs or None,
        catalog=catalog,
    )
    if not packs and normalized_requested_jobs:
        warnings.append("请求的 job 未匹配到可执行巡检 pack，报告将仅展示发现结果。")
    if not packs and not normalized_requested_jobs:
        warnings.append("当前 Prometheus 未发现受支持的固定巡检 job。")

    plan_result = build_plan(
        prometheus_url=normalized_url,
        packs=packs,
        catalog=catalog,
        instance=instance,
        end_time=generated_at,
    )
    if not plan_result.get("ok"):
        raise ValueError(str(plan_result.get("error") or "failed to build inspection plan"))

    execution = execute_plan(
        plan_result["plan"],
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    analysis = analyze_query_results(execution["results"])
    ai_result = _maybe_enrich_with_ai(
        enable_ai=enable_ai,
        llm_settings=llm_settings or LlmSettings.from_env(),
        summary=analysis,
        findings=analysis["findings"],
        warnings=warnings,
    )
    _apply_ai_comments(analysis["findings"], ai_result.get("comments", []))

    payload = {
        "generated_at": isoformat(generated_at),
        "prometheus_url": normalized_url,
        "instance_filter": instance,
        "discovery": discovery,
        "selected_packs": [
            {
                "key": pack.key,
                "title": pack.title,
                "job": pack.job,
                "description": pack.description,
                "metric_count": len(pack.metric_ids),
            }
            for pack in packs
        ],
        "summary": {
            "severity": analysis["severity"],
            "counts": analysis["counts"],
            "finding_count": len(analysis["findings"]),
            "pack_count": len(packs),
        },
        "findings": analysis["findings"],
        "ai_summary": ai_result.get("summary"),
        "warnings": warnings,
        "plan": to_plain(plan_result["plan"]),
    }
    html = render_html(payload)
    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")

    return {
        "ok": True,
        "report_path": output_path,
        "html": html,
        "result": payload,
    }


def execute_plan(
    plan: Mapping[str, Any],
    *,
    headers: Optional[Mapping[str, str]] = None,
    timeout_seconds: float = 20,
) -> Dict[str, Any]:
    client = PrometheusClient(
        base_url=str(plan["prometheus_url"]),
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    results = [execute_task(client, task) for task in plan.get("tasks", [])]
    return {"ok": True, "results": results}


def execute_task(client: PrometheusClient, task: QueryTask) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "task": task,
        "ok": True,
        "current": [],
        "range": [],
        "errors": [],
    }
    try:
        record["current"] = client.query(task.current_promql, time=task.end)
    except PrometheusApiError as exc:
        record["ok"] = False
        record["errors"].append({"stage": "current", "message": str(exc)})

    try:
        record["range"] = client.query_range(
            task.range_promql,
            start=task.start,
            end=task.end,
            step_seconds=task.step_seconds,
        )
    except PrometheusApiError as exc:
        record["ok"] = False
        record["errors"].append({"stage": "range", "message": str(exc)})
    return record


def _maybe_enrich_with_ai(
    *,
    enable_ai: bool,
    llm_settings: Optional[LlmSettings],
    summary: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    warnings: List[str],
) -> Dict[str, Any]:
    if not enable_ai:
        return {"summary": None, "comments": []}
    if llm_settings is None:
        warnings.append("未检测到 LLM 配置，已跳过 AI 补充分析。")
        return {"summary": None, "comments": []}

    try:
        return LlmClient(llm_settings).enrich(summary, findings)
    except LlmError as exc:
        warnings.append(f"AI 补充分析失败，已忽略: {exc}")
        return {"summary": None, "comments": []}


def _apply_ai_comments(findings: List[Dict[str, Any]], comments: Sequence[Mapping[str, Any]]) -> None:
    comments_by_key = {
        str(item.get("finding_key") or "").strip(): str(item.get("comment") or "").strip()
        for item in comments
        if str(item.get("finding_key") or "").strip()
    }
    for finding in findings:
        comment = comments_by_key.get(str(finding.get("finding_key") or ""))
        if comment:
            finding["ai_comment"] = comment
