from __future__ import annotations

import unittest
from datetime import date, timedelta

from time_tree_exporter.cli import _filter_window
from time_tree_exporter.ics import IcsEvent


class FilterWindowTests(unittest.TestCase):
    def test_keeps_old_recurring_event(self) -> None:
        event = IcsEvent(
            uid="weekly",
            summary="Weekly event",
            start=date.today() - timedelta(days=3650),
            end=date.today() - timedelta(days=3649),
            recurrence=("RRULE:FREQ=WEEKLY",),
        )

        self.assertEqual(_filter_window([event], days_back=1, days_ahead=30), [event])

    def test_keeps_old_event_with_parsed_rrule(self) -> None:
        event = IcsEvent(
            uid="yearly",
            summary="Yearly event",
            start=date.today() - timedelta(days=3650),
            end=date.today() - timedelta(days=3649),
            rrule="FREQ=YEARLY",
        )

        self.assertEqual(_filter_window([event], days_back=1, days_ahead=30), [event])

    def test_still_excludes_old_non_recurring_event(self) -> None:
        event = IcsEvent(
            uid="old",
            summary="Old event",
            start=date.today() - timedelta(days=2),
            end=date.today() - timedelta(days=2),
        )

        self.assertEqual(_filter_window([event], days_back=1, days_ahead=30), [])


if __name__ == "__main__":
    unittest.main()
