from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .ics import IcsEvent


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
SYNC_MARKER = "timetreeSync"


def build_calendar_service(credentials_path: Path, token_path: Path):
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def upsert_event(service, calendar_id: str, event: IcsEvent, default_tz: str) -> str:
    existing = find_event_by_timetree_uid(service, calendar_id, event.uid)
    body = to_google_event(event, default_tz)

    if existing:
        service.events().update(calendarId=calendar_id, eventId=existing["id"], body=body).execute()
        return "updated"

    service.events().insert(calendarId=calendar_id, body=body).execute()
    return "created"


def delete_missing_events(service, calendar_id: str, keep_uids: set[str]) -> int:
    deleted = 0
    page_token = None

    while True:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                privateExtendedProperty=f"{SYNC_MARKER}=1",
                maxResults=2500,
                pageToken=page_token,
                showDeleted=False,
                singleEvents=False,
            )
            .execute()
        )
        for item in response.get("items", []):
            private = item.get("extendedProperties", {}).get("private", {})
            uid = private.get("timetreeUid")
            if uid and uid not in keep_uids:
                service.events().delete(calendarId=calendar_id, eventId=item["id"]).execute()
                deleted += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return deleted


def delete_events_by_ical_uids(service, calendar_id: str, i_cal_uids: set[str]) -> int:
    deleted = 0
    for i_cal_uid in sorted(i_cal_uids):
        page_token = None
        while True:
            response = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    iCalUID=i_cal_uid,
                    maxResults=250,
                    pageToken=page_token,
                    showDeleted=False,
                    singleEvents=False,
                )
                .execute()
            )
            for item in response.get("items", []):
                service.events().delete(calendarId=calendar_id, eventId=item["id"]).execute()
                deleted += 1

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    return deleted


def delete_event_by_timetree_uid(service, calendar_id: str, uid: str) -> bool:
    existing = find_event_by_timetree_uid(service, calendar_id, uid)
    if not existing:
        return False
    service.events().delete(calendarId=calendar_id, eventId=existing["id"]).execute()
    return True


def find_event_by_timetree_uid(service, calendar_id: str, uid: str) -> dict[str, Any] | None:
    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            privateExtendedProperty=f"timetreeUid={uid}",
            maxResults=1,
            singleEvents=False,
        )
        .execute()
    )
    items = response.get("items", [])
    return items[0] if items else None


def to_google_event(event: IcsEvent, default_tz: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": event.summary,
        "extendedProperties": {"private": {"timetreeUid": event.uid, SYNC_MARKER: "1"}},
    }

    if event.description:
        body["description"] = event.description
    if event.location:
        body["location"] = event.location
    if event.recurrence:
        body["recurrence"] = list(event.recurrence)
    elif event.rrule:
        body["recurrence"] = [f"RRULE:{event.rrule}"]

    body["start"] = _google_datetime(event.start, default_tz)
    body["end"] = _google_datetime(event.end or _fallback_end(event.start), default_tz)
    return body


def _fallback_end(value: date | datetime) -> date | datetime:
    if isinstance(value, datetime):
        return value + timedelta(hours=1)
    return value + timedelta(days=1)


def _google_datetime(value: date | datetime, default_tz: str) -> dict[str, str]:
    if isinstance(value, datetime):
        payload = {"dateTime": value.isoformat()}
        if value.tzinfo is None:
            payload["timeZone"] = default_tz
        return payload
    return {"date": value.isoformat()}
