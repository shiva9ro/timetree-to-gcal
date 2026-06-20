from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class IcsProperty:
    name: str
    params: dict[str, str]
    value: str


@dataclass(frozen=True)
class IcsEvent:
    uid: str
    summary: str
    start: date | datetime
    end: date | datetime | None
    description: str | None = None
    location: str | None = None
    rrule: str | None = None
    recurrence: tuple[str, ...] = ()

    @property
    def is_all_day(self) -> bool:
        return isinstance(self.start, date) and not isinstance(self.start, datetime)


def parse_ics(text: str, default_tz: str = "Asia/Tokyo") -> list[IcsEvent]:
    events: list[IcsEvent] = []
    current: list[IcsProperty] | None = None

    for line in _unfold_lines(text):
        if line == "BEGIN:VEVENT":
            current = []
            continue
        if line == "END:VEVENT":
            if current is not None:
                event = _build_event(current, default_tz)
                if event is not None:
                    events.append(event)
            current = None
            continue
        if current is not None:
            current.append(_parse_property(line))

    return events


def _unfold_lines(text: str) -> Iterable[str]:
    logical_lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw:
            continue
        if raw.startswith((" ", "\t")) and logical_lines:
            logical_lines[-1] += raw[1:]
        else:
            logical_lines.append(raw)
    return logical_lines


def _parse_property(line: str) -> IcsProperty:
    head, _, value = line.partition(":")
    parts = head.split(";")
    params: dict[str, str] = {}
    for param in parts[1:]:
        key, _, param_value = param.partition("=")
        params[key.upper()] = param_value.strip('"')
    return IcsProperty(parts[0].upper(), params, _unescape(value))


def _build_event(props: list[IcsProperty], default_tz: str) -> IcsEvent | None:
    by_name: dict[str, list[IcsProperty]] = {}
    for prop in props:
        by_name.setdefault(prop.name, []).append(prop)

    uid = _first_value(by_name, "UID")
    dtstart = _first_prop(by_name, "DTSTART")
    if uid is None or dtstart is None:
        return None

    dtend = _first_prop(by_name, "DTEND")
    return IcsEvent(
        uid=uid,
        summary=_first_value(by_name, "SUMMARY") or "(No title)",
        start=_parse_datetime(dtstart, default_tz),
        end=_parse_datetime(dtend, default_tz) if dtend else None,
        description=_first_value(by_name, "DESCRIPTION"),
        location=_first_value(by_name, "LOCATION"),
        rrule=_first_value(by_name, "RRULE"),
    )


def _first_prop(by_name: dict[str, list[IcsProperty]], name: str) -> IcsProperty | None:
    values = by_name.get(name)
    return values[0] if values else None


def _first_value(by_name: dict[str, list[IcsProperty]], name: str) -> str | None:
    prop = _first_prop(by_name, name)
    return prop.value if prop else None


def _parse_datetime(prop: IcsProperty, default_tz: str) -> date | datetime:
    if prop.params.get("VALUE") == "DATE" or _is_date_value(prop.value):
        return datetime.strptime(prop.value, "%Y%m%d").date()

    if prop.value.endswith("Z"):
        return datetime.strptime(prop.value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)

    parsed = datetime.strptime(prop.value, "%Y%m%dT%H%M%S")
    tzid = prop.params.get("TZID", default_tz)
    return parsed.replace(tzinfo=_timezone_for(tzid))


def _timezone_for(tzid: str):
    try:
        return ZoneInfo(tzid)
    except ZoneInfoNotFoundError:
        if tzid == "Asia/Tokyo":
            return timezone(timedelta(hours=9), name="JST")
        raise


def _is_date_value(value: str) -> bool:
    return len(value) == 8 and value.isdigit()


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )
