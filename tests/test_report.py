from datetime import datetime, timezone
import unittest

from prometheus_agent.analysis import analyze_item
from prometheus_agent.models import DataPoint, InspectionResult, TimeSeries
from prometheus_agent.report import generate_html_report


class ReportTests(unittest.TestCase):
    def test_report_contains_item_table_and_details(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        series = TimeSeries(
            labels={"instance": "demo:9100"},
            points=[
                DataPoint(timestamp=now, value=50),
                DataPoint(timestamp=now.replace(hour=1), value=60),
                DataPoint(timestamp=now.replace(hour=2), value=70),
                DataPoint(timestamp=now.replace(hour=3), value=80),
            ],
        )
        item = {
            "id": "cpu",
            "name": "CPU Usage",
            "description": "CPU inspection",
            "promql": "cpu_query",
            "unit": "%",
            "direction": "higher_is_bad",
            "warning": 75,
            "critical": 90,
        }
        analyzed = analyze_item(item, [series], forecast_hours=2)
        result = InspectionResult(
            generated_at=now,
            start=now,
            end=now.replace(hour=3),
            range_hours=3,
            forecast_hours=2,
            items=[analyzed],
            metadata={"prometheus_base_url": "http://localhost:9090"},
        )

        html = generate_html_report(result)

        self.assertIn("Prometheus Inspection Report", html)
        self.assertIn("CPU Usage", html)
        self.assertIn("cpu_query", html)
        self.assertIn("demo:9100", html)


if __name__ == "__main__":
    unittest.main()
