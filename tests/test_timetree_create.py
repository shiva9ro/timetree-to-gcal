from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from time_tree_exporter.timetree_api import (
    build_create_event_payload,
    resolve_label_id,
)


class TimeTreeCreateEventTests(unittest.TestCase):
    def test_builds_timed_event_payload(self) -> None:
        payload = build_create_event_payload(
            {
                "title": "バスケ練習",
                "all_day": False,
                "start_date": "2026-08-01",
                "start_time": "09:00",
                "end_date": "2026-08-01",
                "end_time": "12:00",
                "location": "霞ヶ丘小",
                "note": "5・6年生／8:30集合",
            },
            label_id=3,
        )

        self.assertEqual(payload["title"], "バスケ練習")
        self.assertEqual(payload["label_id"], 3)
        self.assertNotIn("alerts", payload)
        self.assertEqual(payload["start_timezone"], "Asia/Tokyo")
        self.assertEqual(
            payload["start_at"],
            int(datetime(2026, 8, 1, 9, tzinfo=ZoneInfo("Asia/Tokyo")).timestamp() * 1000),
        )

    def test_rejects_missing_time_for_timed_event(self) -> None:
        with self.assertRaisesRegex(ValueError, "start_time"):
            build_create_event_payload(
                {
                    "title": "バスケ練習",
                    "all_day": False,
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-01",
                    "end_time": "12:00",
                }
            )

    def test_resolves_label_name(self) -> None:
        labels = {
            "1": {"name": "予定", "color": "#000"},
            "3": {"name": "バスケ", "color": "#fff"},
        }
        self.assertEqual(resolve_label_id(labels, "バスケ"), 3)

    def test_rejects_unknown_label(self) -> None:
        with self.assertRaisesRegex(ValueError, "label not found"):
            resolve_label_id({"1": {"name": "予定"}}, "バスケ")


if __name__ == "__main__":
    unittest.main()
