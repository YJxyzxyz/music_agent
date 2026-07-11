import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import schedule

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scheduler


class SchedulerTests(unittest.TestCase):
    def tearDown(self):
        schedule.clear()

    def test_configures_daily_and_weekly_jobs_idempotently(self):
        with patch.object(scheduler.settings, "run_time", "09:00"), patch.object(
            scheduler.settings, "weekly_report_enabled", True
        ), patch.object(scheduler.settings, "weekly_report_day", "sunday"), patch.object(
            scheduler.settings, "weekly_report_time", "20:00"
        ):
            scheduler.configure_jobs()
            scheduler.configure_jobs()
        self.assertEqual(1, len(schedule.get_jobs("daily-recommendation")))
        self.assertEqual(1, len(schedule.get_jobs("weekly-report")))


if __name__ == "__main__":
    unittest.main()
