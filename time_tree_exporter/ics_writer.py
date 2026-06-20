from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    start: date | datetime
    end: date | datetime | None = None
    description: str | None = None
    location: str | None = None
    uid: str | None = None
    all_day: bool = False


def events_from_csv(path: Path) -> list[CalendarEvent]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        return [_event_from_row(row) for row in rows]


def write_ics(events: list[CalendarEvent], path: Path, calendar_name: str, time_zone: str) -> None:
    path.write_text(render_ics(events, calendar_name, time_zone), encoding="utf-8", newline="")


def render_ics(events: list[CalendarEvent], calendar_name: str, time_zone: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//time-tree-exporter//ICS Writer//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape_text(calendar_name)}",
        f"X-WR-TIMEZONE:{time_zone}",
    ]

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for event in events:
        lines.extend(_render_event(event, now, time_zone))

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold_line(line) for line in lines) + "\r\n"


def _event_from_row(row: dict[str, str]) -> CalendarEvent:
    summary = _required(row, "summary")
    all_day = _bool(row.get("all_day", ""))
    start = _parse_value(_required(row, "start"), all_day)
    end = _parse_value(row.get("end", ""), all_day) if row.get("end") else None

    return CalendarEvent(
        summary=summary,
        start=start,
        end=end,
        description=_blank_to_none(row.get("description")),
        location=_blank_to_none(row.get("location")),
        uid=_blank_to_none(row.get("uid")),
        all_day=all_day,
    )


def _render_event(event: CalendarEvent, dtstamp: str, time_zone: str) -> list[str]:
    uid = event.uid or _make_uid(event)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_escape_text(uid)}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{_escape_text(event.summary)}",
    ]

    if event.all_day:
        start = _as_date(event.start)
        end = _as_date(event.end) + timedelta(days=1) if event.end else start + timedelta(days=1)
        lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
    else:
        lines.append(f"DTSTART;TZID={time_zone}:{_as_datetime(event.start).strftime('%Y%m%dT%H%M%S')}")
        end = _as_datetime(event.end) if event.end else _as_datetime(event.start) + timedelta(hours=1)
        lines.append(f"DTEND;TZID={time_zone}:{end.strftime('%Y%m%dT%H%M%S')}")

    if event.description:
        lines.append(f"DESCRIPTION:{_escape_text(event.description)}")
    if event.location:
        lines.append(f"LOCATION:{_escape_text(event.location)}")

    lines.append("END:VEVENT")
    return lines


def _parse_value(value: str, all_day: bool) -> date | datetime:
    value = value.strip()
    if all_day:
        return date.fromisoformat(value)
    return datetime.fromisoformat(value)


def _required(row: dict[str, str], name: str) -> str:
    value = row.get(name, "").strip()
    if not value:
        raise ValueError(f"CSV column '{name}' is required.")
    return value


def _blank_to_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _as_date(value: date | datetime | None) -> date:
    if value is None:
        raise ValueError("date value is required.")
    if isinstance(value, datetime):
        return value.date()
    return value


def _as_datetime(value: date | datetime | None) -> datetime:
    if value is None:
        raise ValueError("datetime value is required.")
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())


def _make_uid(event: CalendarEvent) -> str:
    raw = "|".join(
        [
            event.summary,
            event.start.isoformat(),
            event.end.isoformat() if event.end else "",
            event.location or "",
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{digest}@time-tree-exporter.local"


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold_line(line: str) -> str:
    if len(line) <= 75:
        return line

    chunks = [line[:75]]
    line = line[75:]
    while line:
        chunks.append(" " + line[:74])
        line = line[74:]
    return "\r\n".join(chunks)
