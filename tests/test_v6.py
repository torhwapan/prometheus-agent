from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from prometheus_agent_v6.analysis import analyze_query_results
from prometheus_agent_v6.catalog import load_catalog, select_packs
from prometheus_agent_v6.models import DataPoint, QueryTask, TimeSeries
from prometheus_agent_v6.report import render_html
from prometheus_agent_v6.service import inspect_prometheus


def make_points(values):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [DataPoint(timestamp=start + timedelta(hours=index), value=value) for index, value in enumerate(values)]


class V6Tests(unittest.TestCase):
    def test_select_packs_from_discovered_jobs(self):
        catalog = load_catalog()
        packs = select_packs(["redis_exporter", "java_jmx"], catalog=catalog)

        self.assertEqual([pack.job for pack in packs], ["java_jmx", "redis_exporter"])

    def test_analysis_marks_rising_series_as_critical(self):
        catalog = load_catalog()
        spec = catalog["redis_exporter"][1]
        task = QueryTask(
            task_id="redis:memory",
            pack_key="redis-fixed-inspection",
            pack_title="Redis 固定巡检",
            job=spec.job,
            metric_id=spec.id,
            metric_name=spec.name,
            instance="127.0.0.1:9095",
            current_promql=spec.current_promql,
            range_promql=spec.range_promql,
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 2, tzinfo=timezone.utc),
            step_seconds=60,
            spec=spec,
        )
        result = analyze_query_results(
            [
                {
                    "task": task,
                    "ok": True,
                    "current": [TimeSeries(labels={"instance": "127.0.0.1:9095"}, points=[make_points([95])[-1]])],
                    "range": [TimeSeries(labels={"instance": "127.0.0.1:9095"}, points=make_points([60, 70, 80, 90, 95]))],
                    "errors": [],
                }
            ]
        )

        self.assertEqual(result["severity"], "critical")
        self.assertEqual(result["findings"][0]["severity"], "critical")

    def test_render_html_contains_fixed_sections(self):
        html = render_html(
            {
                "generated_at": "2026-01-01T00:00:00Z",
                "prometheus_url": "http://localhost:9090",
                "instance_filter": None,
                "discovery": {"normalized_jobs": ["redis_exporter"], "active_target_count": 2},
                "selected_packs": [
                    {"title": "Redis 固定巡检", "job": "redis_exporter", "metric_count": 7, "description": "desc"}
                ],
                "summary": {
                    "severity": "warning",
                    "counts": {"critical": 0, "warning": 1, "info": 0, "ok": 2, "unknown": 0},
                    "finding_count": 3,
                    "pack_count": 1,
                },
                "findings": [
                    {
                        "severity": "warning",
                        "pack_title": "Redis 固定巡检",
                        "job": "redis_exporter",
                        "instance": "127.0.0.1:9095",
                        "metric_id": "redis_memory_usage",
                        "metric_name": "Redis Memory Usage",
                        "current_value": 88.2,
                        "reason": "当前值已达到预警阈值。",
                        "analysis": {"unit": "%"},
                        "ai_comment": "建议确认 maxmemory 与淘汰策略。",
                        "labels": {"instance": "127.0.0.1:9095"},
                    }
                ],
                "ai_summary": "Redis 内存压力升高。",
                "warnings": [],
            }
        )

        self.assertIn("Prometheus 固定巡检报告", html)
        self.assertIn("Redis 固定巡检", html)
        self.assertIn("AI 补充摘要", html)

    @patch("prometheus_agent_v6.service.execute_plan")
    @patch("prometheus_agent_v6.service.PrometheusDiscoveryClient")
    def test_service_can_generate_html_without_ai(self, discovery_cls, execute_plan_mock):
        discovery_cls.return_value.snapshot.return_value = {
            "raw_jobs": ["redis_exporter"],
            "normalized_jobs": ["redis_exporter"],
            "instances_by_job": {"redis_exporter": ["127.0.0.1:9095"]},
            "active_target_count": 1,
        }
        catalog = load_catalog()
        spec = catalog["redis_exporter"][0]
        task = QueryTask(
            task_id="redis:up",
            pack_key="redis-fixed-inspection",
            pack_title="Redis 固定巡检",
            job=spec.job,
            metric_id=spec.id,
            metric_name=spec.name,
            instance="127.0.0.1:9095",
            current_promql=spec.current_promql,
            range_promql=spec.range_promql,
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 2, tzinfo=timezone.utc),
            step_seconds=60,
            spec=spec,
        )
        execute_plan_mock.return_value = {
            "ok": True,
            "results": [
                {
                    "task": task,
                    "ok": True,
                    "current": [TimeSeries(labels={"instance": "127.0.0.1:9095"}, points=[make_points([1])[-1]])],
                    "range": [TimeSeries(labels={"instance": "127.0.0.1:9095"}, points=make_points([1, 1, 1, 1]))],
                    "errors": [],
                }
            ],
        }

        result = inspect_prometheus(
            "http://localhost:9090",
            enable_ai=False,
        )

        self.assertTrue(result["ok"])
        self.assertIn("Prometheus 固定巡检报告", result["html"])
        self.assertEqual(result["result"]["summary"]["pack_count"], 1)


if __name__ == "__main__":
    unittest.main()
