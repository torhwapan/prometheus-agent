import unittest

from prometheus_agent.grafana import extract_thresholds_from_rules, merge_thresholds
from prometheus_agent.inspection_plan import build_inspection_plan, validate_inspection_plan
from prometheus_agent.metric_catalog import select_metric_specs
from prometheus_agent.target_resolver import resolve_target


class ToolTests(unittest.TestCase):
    def test_resolve_target_by_alias(self):
        result = resolve_target("127.0.0.1", domain="redis")

        self.assertTrue(result["ok"])
        self.assertEqual(result["target"]["id"], "local-dev")
        self.assertIn("redis", result["query_scope"]["job_patterns"])

    def test_metric_catalog_selects_domain(self):
        result = select_metric_specs("redis")

        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["domain"], "redis")

    def test_build_inspection_plan(self):
        result = build_inspection_plan("localhost", "redis", range_hours=6, step_seconds=60)

        self.assertTrue(result["ok"])
        plan = result["plan"]
        self.assertEqual(plan["target"]["id"], "local-dev")
        self.assertEqual(plan["scope"]["domain"], "redis")
        self.assertEqual(plan["time"]["range_hours"], 6)
        self.assertTrue(validate_inspection_plan(plan)["ok"])

    def test_grafana_threshold_extraction_and_merge(self):
        rules = [
            {
                "uid": "rule-1",
                "title": "redis_memory_usage high",
                "labels": {"severity": "critical", "metric_id": "redis_memory_usage"},
                "condition": {
                    "evaluator": {
                        "type": "gt",
                        "params": [88],
                    }
                },
            }
        ]
        thresholds = extract_thresholds_from_rules(rules, metric_ids=["redis_memory_usage"])
        merged = merge_thresholds(
            [
                {
                    "id": "redis_memory_usage",
                    "name": "Redis Memory Usage",
                    "critical": 90,
                    "direction": "higher_is_bad",
                }
            ],
            thresholds,
        )

        self.assertEqual(thresholds[0]["value"], 88)
        self.assertEqual(merged[0]["critical"], 88)
        self.assertEqual(merged[0]["threshold_source"], "grafana_alert_rule")


if __name__ == "__main__":
    unittest.main()
