from __future__ import annotations

import json
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


def _next_since(events: list[dict[str, Any]], default: int = 0) -> int:
    updated_values = [int(event["updated_at"]) for event in events if event.get("updated_at")]
    return max(updated_values) + 1 if updated_values else default


def _label_name(label_id: Any, labels: dict[str, dict[str, Any]]) -> str | None:
    if label_id is None:
        return None
    key = str(label_id).split(",")[-1]
    label = labels.get(key)
    return label.get("name") if label else None
