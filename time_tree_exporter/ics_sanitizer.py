from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from icalendar import Calendar, Event


KEEP_EVENT_PROPERTIES = {
    "SUMMARY",
    "DTSTART",
    "DTEND",
    "DTSTAMP",
    "UID",
    "DESCRIPTION",
    "LOCATION",
}


def sanitize_ics_for_google(source: Path, output: Path) -> int:
    calendar = Calendar.from_ical(source.read_bytes())
    clean = Calendar()
    clean.add("version", "2.0")
    clean.add("prodid", "-//time-tree-exporter//Google Import Sanitizer//EN")
    clean.add("calscale", "GREGORIAN")
    clean.add("method", "PUBLISH")

    count = 0
    for component in calendar.walk("VEVENT"):
        clean_event = _clean_event(component)
        clean.add_component(clean_event)
        count += 1

    output.write_bytes(clean.to_ical())
    return count


def _clean_event(component: Event) -> Event:
    event = Event()
    for name in KEEP_EVENT_PROPERTIES:
        value = component.get(name)
        if value is not None:
            event.add(name.lower(), _property_value(value, name))

    if not event.get("DTSTAMP"):
        event.add("dtstamp", datetime.now(timezone.utc))

    _normalize_uid(event)
    _ensure_end(event)
    return event


def _property_value(value, name: str):
    if hasattr(value, "dt"):
        dt = value.dt
        if name in {"DTSTART", "DTEND", "DTSTAMP"} and isinstance(dt, datetime):
            if dt.tzinfo is None:
                return dt
            return dt.astimezone(timezone.utc)
        return dt
    return str(value)


def _normalize_uid(event: Event) -> None:
    uid = event.get("UID")
    if uid is None:
        return
    uid_text = str(uid)
    if "@" not in uid_text:
        event["UID"] = f"{uid_text}@timetree.local"


def _ensure_end(event: Event) -> None:
    if event.get("DTEND") is not None:
        return

    start = event.get("DTSTART")
    if start is None:
        return

    start_value: Any = start.dt
    if isinstance(start_value, datetime):
        event.add("dtend", start_value)
    elif isinstance(start_value, date):
        event.add("dtend", start_value)
