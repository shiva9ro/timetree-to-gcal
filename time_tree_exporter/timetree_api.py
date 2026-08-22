from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .ics import IcsEvent


API_BASE_URL = "https://timetreeapp.com/api/v1"
API_HEADERS = {"Content-Type": "application/json", "X-Timetreea": "web/2.1.0/en"}


@dataclass(frozen=True)
class FetchResult:
    events: list[dict[str, Any]]
    since: int
    request_count: int


class TimeTreeClient:
    def __init__(self, email: str, password: str):
        self.session = requests.Session()
        self._csrf_token: str | None = None
        self._login(email, password)

    def _login(self, email: str, password: str) -> None:
        response = self.session.put(
            f"{API_BASE_URL}/auth/email/signin",
            json={"uid": email, "password": password, "uuid": uuid.uuid4().hex},
            headers=API_HEADERS,
            timeout=20,
        )
        response.raise_for_status()

    def calendar_by_code(self, calendar_code: str) -> dict[str, Any]:
        response = self.session.get(
            f"{API_BASE_URL}/calendars?since=0",
            headers=API_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        for calendar in response.json().get("calendars", []):
            if calendar.get("alias_code") == calendar_code:
                return calendar
        raise ValueError(f"TimeTree calendar code not found: {calendar_code}")

    def fetch_all_events(self, calendar_id: int) -> FetchResult:
        events: list[dict[str, Any]] = []
        url = f"{API_BASE_URL}/calendar/{calendar_id}/events/sync"
        request_count = 0

        while True:
            response = self.session.get(url, headers=API_HEADERS, timeout=30)
            response.raise_for_status()
            payload = response.json()
            request_count += 1
            events.extend(payload.get("events", []))
            if not payload.get("chunk"):
                break
            url = f"{API_BASE_URL}/calendar/{calendar_id}/events/sync?since={payload['since']}"

        since = _next_since(events)
        return FetchResult(events, since, request_count)

    def fetch_labels(self, calendar_id: int) -> dict[str, dict[str, Any]]:
        response = self.session.get(
            f"{API_BASE_URL}/calendar/{calendar_id}/labels",
            headers=API_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        labels = {}
        for label in response.json().get("calendar_labels", []):
            label_id = label.get("id")
            if label_id is not None:
                labels[str(label_id)] = {
                    "name": label.get("name") or "",
                    "color": label.get("color"),
                }
        return labels

    def create_event(self, calendar_id: int, event: dict[str, Any]) -> dict[str, Any]:
        headers = {
            **API_HEADERS,
            "X-CSRF-Token": self._get_csrf_token(),
        }
        response = self.session.post(
            f"{API_BASE_URL}/calendar/{calendar_id}/event",
            json=event,
            headers=headers,
            timeout=20,
        )
        if not response.ok:
            detail = response.text.strip()
            raise RuntimeError(
                f"TimeTree create event failed ({response.status_code}): {detail}"
            )
        return response.json()

    def _get_csrf_token(self) -> str:
        if self._csrf_token:
            return self._csrf_token
        response = self.session.get(
            "https://timetreeapp.com/calendars",
            headers=API_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        match = re.search(
            r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)',
            response.text,
            flags=re.IGNORECASE,
        )
        if not match:
            raise RuntimeError("TimeTree CSRF token was not found.")
        self._csrf_token = match.group(1)
        return self._csrf_token

    def fetch_changed_events(self, calendar_id: int, since: int) -> FetchResult:
        events: list[dict[str, Any]] = []
        cursor = since
        request_count = 0

        while True:
            response = self.session.get(
                f"{API_BASE_URL}/calendar/{calendar_id}/events?since={cursor}",
                headers=API_HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            request_count += 1
            page_events = payload.get("events", [])
            events.extend(page_events)
            next_cursor = max(cursor, int(payload.get("since", cursor)), _next_since(page_events, cursor))
            if not payload.get("chunk"):
                cursor = next_cursor
                break
            if next_cursor <= cursor:
                raise RuntimeError("TimeTree delta cursor did not advance.")
            cursor = next_cursor

        return FetchResult(events, cursor, request_count)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def build_create_event_payload(
    event: dict[str, Any],
    *,
    label_id: int | None = None,
    time_zone: str = "Asia/Tokyo",
) -> dict[str, Any]:
    title = str(event.get("title") or "").strip()
    if not title:
        raise ValueError("title is required.")

    all_day = bool(event.get("all_day"))
    start_date = _parse_iso_date(event.get("start_date"), "start_date")
    end_date = _parse_iso_date(event.get("end_date") or event.get("start_date"), "end_date")
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date.")

    payload: dict[str, Any] = {
        "title": title,
        "all_day": all_day,
    }
    if all_day:
        payload["start_at"] = _epoch_milliseconds(start_date, None, "UTC")
        payload["end_at"] = _epoch_milliseconds(end_date, None, "UTC")
    else:
        start_time = _parse_iso_time(event.get("start_time"), "start_time")
        end_time = _parse_iso_time(event.get("end_time"), "end_time")
        payload["start_at"] = _epoch_milliseconds(start_date, start_time, time_zone)
        payload["end_at"] = _epoch_milliseconds(end_date, end_time, time_zone)
        if payload["end_at"] < payload["start_at"]:
            raise ValueError("Event end must not be before event start.")
        payload["start_timezone"] = time_zone
        payload["end_timezone"] = time_zone

    for source, target in (
        ("location", "location"),
        ("url", "url"),
        ("note", "note"),
        ("recurrences", "recurrences"),
        ("attendees", "attendees"),
        ("alerts", "alerts"),
    ):
        value = event.get(source)
        if value not in (None, "", []):
            payload[target] = value
    if label_id is not None:
        payload["label_id"] = label_id
    return payload


def resolve_label_id(
    labels: dict[str, dict[str, Any]], label_name: str | None
) -> int | None:
    if not label_name:
        return None
    matches = [
        int(label_id)
        for label_id, label in labels.items()
        if str(label.get("name") or "").strip().casefold() == label_name.strip().casefold()
    ]
    if not matches:
        raise ValueError(f"TimeTree label not found: {label_name}")
    if len(matches) > 1:
        raise ValueError(f"TimeTree label name is ambiguous: {label_name}")
    return matches[0]


def merge_events(
    cached_events: list[dict[str, Any]], changed_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_uid = {event["uuid"]: event for event in cached_events if event.get("uuid")}
    for event in changed_events:
        if event.get("uuid"):
            by_uid[event["uuid"]] = event
    return list(by_uid.values())


def to_ics_event(
    raw: dict[str, Any],
    labels: dict[str, dict[str, Any]] | None = None,
    prefix_label: bool = True,
) -> IcsEvent | None:
    if raw.get("deactivated_at") is not None:
        return None
    if raw.get("type") == 1 or raw.get("category") == 2:
        return None

    all_day = bool(raw.get("all_day"))
    start = _event_datetime(raw.get("start_at"), raw.get("start_timezone"), all_day)
    end = _event_datetime(raw.get("end_at"), raw.get("end_timezone"), all_day)
    if all_day and isinstance(end, date):
        end += timedelta(days=1)

    recurrences = tuple(str(value) for value in raw.get("recurrences") or [])
    title = raw.get("title") or "(No title)"
    label_name = _label_name(raw.get("label_id"), labels or {})
    if prefix_label and label_name:
        title = f"【{label_name}】{title}"

    return IcsEvent(
        uid=str(raw["uuid"]),
        summary=title,
        start=start,
        end=end,
        description=raw.get("note") or None,
        location=raw.get("location") or None,
        recurrence=recurrences,
    )


def _event_datetime(value: int | None, tzid: str | None, all_day: bool) -> date | datetime:
    if value is None:
        raise ValueError("TimeTree event timestamp is missing.")
    tz = ZoneInfo(tzid or "Asia/Tokyo")
    parsed = datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone(tz)
    return parsed.date() if all_day else parsed


def _parse_iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} is required in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD format.") from exc


def _parse_iso_time(value: Any, field: str):
    if not isinstance(value, str):
        raise ValueError(f"{field} is required in HH:MM format for timed events.")
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(f"{field} must use HH:MM format.") from exc


def _epoch_milliseconds(day: date, clock, time_zone: str) -> int:
    if clock is None:
        value = datetime.combine(day, datetime.min.time(), tzinfo=ZoneInfo(time_zone))
    else:
        value = datetime.combine(day, clock, tzinfo=ZoneInfo(time_zone))
    return int(value.timestamp() * 1000)


def _next_since(events: list[dict[str, Any]], default: int = 0) -> int:
    updated_values = [int(event["updated_at"]) for event in events if event.get("updated_at")]
    return max(updated_values) + 1 if updated_values else default


def _label_name(label_id: Any, labels: dict[str, dict[str, Any]]) -> str | None:
    if label_id is None:
        return None
    key = str(label_id).split(",")[-1]
    label = labels.get(key)
    return label.get("name") if label else None
