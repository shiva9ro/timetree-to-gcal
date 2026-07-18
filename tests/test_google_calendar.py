from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from time_tree_exporter.google_calendar import to_google_event
from time_tree_exporter.ics import IcsEvent


class ToGoogleEventTests(unittest.TestCase):
    def test_recurring_event_has_explicit_time_zone(self) -> None:
        event = IcsEvent(
            uid="weekly",
            summary="Weekly event",
            start=datetime(2026, 7, 18, 9, 0, tzinfo=timezone(timedelta(hours=9))),
            end=datetime(2026, 7, 18, 10, 0, tzinfo=timezone(timedelta(hours=9))),
            recurrence=("RRULE:FREQ=WEEKLY",),
        )

        body = to_google_event(event, "Asia/Tokyo")

        self.assertEqual(body["start"]["timeZone"], "Asia/Tokyo")
        self.assertEqual(body["end"]["timeZone"], "Asia/Tokyo")

    def test_aware_non_recurring_event_does_not_add_time_zone(self) -> None:
        event = IcsEvent(
            uid="single",
            summary="Single event",
            start=datetime(2026, 7, 18, 9, 0, tzinfo=timezone(timedelta(hours=9))),
            end=datetime(2026, 7, 18, 10, 0, tzinfo=timezone(timedelta(hours=9))),
        )

        body = to_google_event(event, "Asia/Tokyo")

        self.assertNotIn("timeZone", body["start"])
        self.assertNotIn("timeZone", body["end"])


if __name__ == "__main__":
    unittest.main()
