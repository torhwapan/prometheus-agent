from datetime import datetime, timedelta, timezone
import unittest

from prometheus_agent.analysis import analyze_item
from prometheus_agent.models import DataPoint, TimeSeries


def make_series(values, labels=None):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return TimeSeries(
        labels=labels or {"instance": "demo:9100"},
        points=[
            DataPoint(timestamp=start + timedelta(hours=index), value=value)
            for index, value in enumerate(values)
        ],
    )


class AnalysisTests(unittest.TestCase):
    def test_forecast_crossing_threshold_is_critical(self):
        item = {
            "id": "cpu",
            "name": "CPU",
            "promql": "cpu_query",
            "unit": "%",
            "direction": "higher_is_bad",
            "warning": 80,
            "critical": 90,
        }

        result = analyze_item(item, [make_series([50, 55, 60, 65, 70, 75])], forecast_hours=12)

        self.assertEqual(result.severity, "critical")
        self.assertIn("Forecast reaches", result.summary)
        self.assertGreater(result.series[0].forecast, 90)

    def test_stable_series_is_ok(self):
        item = {
            "id": "memory",
            "name": "Memory",
            "promql": "memory_query",
            "unit": "%",
            "direction": "higher_is_bad",
            "warning": 80,
            "critical": 90,
        }

        result = analyze_item(item, [make_series([40, 41, 39, 40, 40])], forecast_hours=24)

        self.assertEqual(result.severity, "ok")
        self.assertEqual(result.series[0].status, "Healthy")

    def test_lower_is_bad_forecast_warning(self):
        item = {
            "id": "availability",
            "name": "Availability",
            "promql": "availability_query",
            "unit": "%",
            "direction": "lower_is_bad",
            "warning": 20,
            "critical": 10,
        }

        result = analyze_item(item, [make_series([50, 45, 40, 35, 30])], forecast_hours=3)

        self.assertEqual(result.severity, "warning")
        self.assertLess(result.series[0].forecast, 20)

    def test_no_series_is_unknown(self):
        item = {"id": "disk", "name": "Disk", "promql": "disk_query"}

        result = analyze_item(item, [], forecast_hours=24)

        self.assertEqual(result.severity, "unknown")
        self.assertIn("no time series", result.summary)


if __name__ == "__main__":
    unittest.main()
