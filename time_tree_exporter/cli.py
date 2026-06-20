from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen

from .env import load_env_file
from .ics import IcsEvent, parse_ics
from .ics_sanitizer import sanitize_ics_for_google
from .ics_writer import events_from_csv, write_ics


def main() -> int:
    load_env_file(Path(".env"))
    parser = argparse.ArgumentParser(prog="time-tree-exporter")
    subcommands = parser.add_subparsers(dest="command", required=True)

    sync = subcommands.add_parser("sync", help="Copy TimeTree ICS events to Google Calendar")
    source = sync.add_mutually_exclusive_group(required=True)
    source.add_argument("--ics", type=Path, help="Path to a TimeTree ICS file")
    source.add_argument("--ics-url", help="URL for a TimeTree ICS feed")
    sync.add_argument("--calendar-id", required=True, help="Destination Google Calendar ID")
    sync.add_argument("--credentials", type=Path, default=Path("credentials.json"))
    sync.add_argument("--token", type=Path, default=Path("token.json"))
    sync.add_argument("--time-zone", default="Asia/Tokyo")
    sync.add_argument("--days-back", type=int, default=7)
    sync.add_argument("--days-ahead", type=int, default=180)
    sync.add_argument("--dry-run", action="store_true")

    make_ics = subcommands.add_parser("make-ics", help="Create an ICS file from a CSV file")
    make_ics.add_argument("--csv", type=Path, required=True, help="Source CSV file")
    make_ics.add_argument("--output", type=Path, required=True, help="Output ICS file")
    make_ics.add_argument("--calendar-name", default="Exported calendar")
    make_ics.add_argument("--time-zone", default="Asia/Tokyo")

    sanitize = subcommands.add_parser("sanitize-ics", help="Create a Google-import-friendly ICS file")
    sanitize.add_argument("--ics", type=Path, required=True, help="Source ICS file")
    sanitize.add_argument("--output", type=Path, required=True, help="Output ICS file")

    delete_ics = subcommands.add_parser("delete-ics-events", help="Delete Google Calendar events whose iCalUIDs appear in an ICS file")
    delete_ics.add_argument("--ics", type=Path, required=True, help="ICS file containing events to delete")
    delete_ics.add_argument("--calendar-id", required=True, help="Google Calendar ID")
    delete_ics.add_argument("--credentials", type=Path, default=Path("credentials.json"))
    delete_ics.add_argument("--token", type=Path, default=Path("token.json"))
    delete_ics.add_argument("--dry-run", action="store_true")

    sync_tt = subcommands.add_parser("sync-timetree", help="Fetch TimeTree events and sync them to Google Calendar")
    sync_tt.add_argument(
        "--calendar-id",
        default=os.environ.get("GOOGLE_CALENDAR_ID"),
        help="Destination Google Calendar ID. Can also use GOOGLE_CALENDAR_ID.",
    )
    sync_tt.add_argument("--email", help="TimeTree email address. Can also use TIMETREE_EMAIL.")
    sync_tt.add_argument("--calendar-code", help="TimeTree calendar code")
    sync_tt.add_argument("--output", type=Path, default=Path("timetree.ics"), help="Raw TimeTree ICS output path")
    sync_tt.add_argument("--credentials", type=Path, default=Path("credentials.json"))
    sync_tt.add_argument("--token", type=Path, default=Path("token.json"))
    sync_tt.add_argument("--time-zone", default="Asia/Tokyo")
    sync_tt.add_argument("--days-back", type=int, default=1)
    sync_tt.add_argument("--days-ahead", type=int, default=30)
    sync_tt.add_argument("--skip-fetch", action="store_true", help="Use existing --output ICS without fetching TimeTree")
    sync_tt.add_argument("--dry-run", action="store_true")
    sync_tt.add_argument("--delete-missing", action="store_true", help="Delete Google events previously synced by this tool but missing from the current TimeTree export")
    sync_tt.add_argument("--state", type=Path, default=Path("sync-state.json"))
    sync_tt.add_argument("--cache", type=Path, default=Path("timetree-cache.json"))
    sync_tt.add_argument("--labels-cache", type=Path, default=Path("timetree-labels.json"))
    sync_tt.add_argument("--full-refresh", action="store_true", help="Discard the delta cursor and fetch all TimeTree events")
    sync_tt.add_argument("--no-label-prefix", action="store_true", help="Do not prefix Google event titles with TimeTree label names")

    args = parser.parse_args()
    if args.command == "sync":
        return run_sync(args)
    if args.command == "make-ics":
        return run_make_ics(args)
    if args.command == "sanitize-ics":
        return run_sanitize_ics(args)
    if args.command == "delete-ics-events":
        return run_delete_ics_events(args)
    if args.command == "sync-timetree":
        return run_sync_timetree(args)
    return 1


def run_make_ics(args: argparse.Namespace) -> int:
    events = events_from_csv(args.csv)
    write_ics(events, args.output, args.calendar_name, args.time_zone)
    print(f"Wrote {len(events)} event(s) to {args.output}")
    return 0


def run_sanitize_ics(args: argparse.Namespace) -> int:
    count = sanitize_ics_for_google(args.ics, args.output)
    print(f"Wrote {count} event(s) to {args.output}")
    return 0


def run_delete_ics_events(args: argparse.Namespace) -> int:
    events = parse_ics(_read_ics(args.ics, None))
    uids = {event.uid for event in events}
    if args.dry_run:
        print(f"Would delete events matching {len(uids)} iCalUID(s) from {args.calendar_id}.")
        return 0

    if not args.credentials.exists():
        print(f"Missing Google OAuth credentials: {args.credentials}")
        return 2

    from .google_calendar import build_calendar_service, delete_events_by_ical_uids

    service = build_calendar_service(args.credentials, args.token)
    deleted = delete_events_by_ical_uids(service, args.calendar_id, uids)
    print(f"Deleted {deleted} event(s).")
    return 0


def run_sync_timetree(args: argparse.Namespace) -> int:
    if not args.skip_fetch:
        return _run_delta_sync(args)

    sync_args = argparse.Namespace(
        ics=args.output,
        ics_url=None,
        calendar_id=args.calendar_id,
        credentials=args.credentials,
        token=args.token,
        time_zone=args.time_zone,
        days_back=args.days_back,
        days_ahead=args.days_ahead,
        dry_run=args.dry_run,
        delete_missing=args.delete_missing,
    )
    return run_sync(sync_args)


def _run_delta_sync(args: argparse.Namespace) -> int:
    from .google_calendar import (
        build_calendar_service,
        delete_event_by_timetree_uid,
        upsert_event,
    )
    from .timetree_api import (
        TimeTreeClient,
        load_json,
        merge_events,
        to_ics_event,
        write_json,
    )

    if not args.calendar_id:
        print("--calendar-id or GOOGLE_CALENDAR_ID is required.")
        return 2

    email = args.email or os.environ.get("TIMETREE_EMAIL")
    password = os.environ.get("TIMETREE_PASSWORD")
    calendar_code = args.calendar_code or os.environ.get("TIMETREE_CALENDAR_CODE")
    if not email or not password or not calendar_code:
        print("TIMETREE_EMAIL, TIMETREE_PASSWORD and TIMETREE_CALENDAR_CODE are required.")
        return 2

    client = TimeTreeClient(email, password)
    calendar = client.calendar_by_code(calendar_code)
    state = load_json(args.state, {})
    cached_events = load_json(args.cache, [])
    labels = load_json(args.labels_cache, {})
    state_matches = (
        state.get("calendar_code") == calendar_code
        and state.get("calendar_id") == calendar["id"]
        and state.get("since") is not None
        and bool(cached_events)
    )
    full_refresh = args.full_refresh or not state_matches

    if full_refresh:
        result = client.fetch_all_events(calendar["id"])
        merged_events = result.events
        changed_events = result.events
        mode = "full"
    else:
        result = client.fetch_changed_events(calendar["id"], int(state["since"]))
        changed_events = result.events
        merged_events = merge_events(cached_events, changed_events)
        mode = "delta"

    known_label_ids = set(labels)
    changed_label_ids = {
        str(raw.get("label_id")).split(",")[-1]
        for raw in changed_events
        if raw.get("label_id") is not None
    }
    labels_refreshed = full_refresh or not labels or not changed_label_ids <= known_label_ids
    if labels_refreshed:
        labels = client.fetch_labels(calendar["id"])

    active_events = [
        event
        for raw in merged_events
        if (
            event := to_ics_event(
                raw,
                labels=labels,
                prefix_label=not args.no_label_prefix,
            )
        )
        is not None
    ]
    window_events = _filter_window(active_events, args.days_back, args.days_ahead)
    deactivated = [raw for raw in changed_events if raw.get("deactivated_at") is not None]
    today = date.today()
    window_start = today - timedelta(days=args.days_back)
    window_end = today + timedelta(days=args.days_ahead)

    previous_start = _parse_optional_date(state.get("window_start"))
    previous_end = _parse_optional_date(state.get("window_end"))
    previous_window_known = previous_start is not None and previous_end is not None

    format_version = 2 if not args.no_label_prefix else 1
    format_changed = state.get("format_version") != format_version
    if full_refresh or not previous_window_known or format_changed or labels_refreshed:
        google_upserts = window_events
    else:
        changed_uids = {raw.get("uuid") for raw in changed_events if raw.get("uuid")}
        changed_window_events = [event for event in window_events if event.uid in changed_uids]
        entering_window_events = [
            event
            for event in window_events
            if not previous_start <= _event_date(event.start) <= previous_end
        ]
        google_upserts = _unique_events(changed_window_events + entering_window_events)

    google_upsert_uids = {event.uid for event in google_upserts}
    google_deletes = {
        raw["uuid"]
        for raw in changed_events
        if raw.get("uuid") and raw["uuid"] not in google_upsert_uids
    }

    print(
        f"TimeTree {mode}: requests={result.request_count} changed={len(changed_events)} "
        f"cached={len(merged_events)} window={len(window_events)} deleted={len(deactivated)} "
        f"labels_refreshed={str(labels_refreshed).lower()} "
        f"google_upserts={len(google_upserts)} google_deletes={len(google_deletes)}"
    )
    if args.dry_run:
        print("Dry-run: cache, cursor and Google Calendar were not changed.")
        return 0

    counts = {"created": 0, "updated": 0, "deleted": 0}
    if google_upserts or (google_deletes and not full_refresh):
        if not args.credentials.exists():
            print(f"Missing Google OAuth credentials: {args.credentials}")
            return 2
        service = build_calendar_service(args.credentials, args.token)
        for event in google_upserts:
            action = upsert_event(service, args.calendar_id, event, args.time_zone)
            counts[action] += 1

        if not full_refresh:
            for uid in sorted(google_deletes):
                if delete_event_by_timetree_uid(service, args.calendar_id, uid):
                    counts["deleted"] += 1

    new_state = {
        "version": 1,
        "calendar_code": calendar_code,
        "calendar_id": calendar["id"],
        "since": result.since,
        "format_version": format_version,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "updated_at": datetime.now().astimezone().isoformat(),
    }
    write_json(args.cache, merged_events)
    write_json(args.labels_cache, labels)
    write_json(args.state, new_state)
    print(
        f"Google: created={counts['created']} updated={counts['updated']} "
        f"deleted={counts['deleted']} next_since={result.since}"
    )
    return 0


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _unique_events(events: list[IcsEvent]) -> list[IcsEvent]:
    return list({event.uid: event for event in events}.values())


def run_sync(args: argparse.Namespace) -> int:
    text = _read_ics(args.ics, args.ics_url)
    events = _filter_window(
        parse_ics(text, default_tz=args.time_zone),
        days_back=args.days_back,
        days_ahead=args.days_ahead,
    )

    if args.dry_run:
        for event in events:
            print(f"dry-run\t{event.start}\t{event.summary}\t{event.uid}")
        print(f"{len(events)} event(s) matched.")
        return 0

    if not args.credentials.exists():
        print(f"Missing Google OAuth credentials: {args.credentials}")
        return 2

    from .google_calendar import build_calendar_service, delete_missing_events, upsert_event

    service = build_calendar_service(args.credentials, args.token)
    counts = {"created": 0, "updated": 0}
    for event in events:
        result = upsert_event(service, args.calendar_id, event, args.time_zone)
        counts[result] += 1
        print(f"{result}\t{event.start}\t{event.summary}")

    deleted = 0
    if getattr(args, "delete_missing", False):
        deleted = delete_missing_events(service, args.calendar_id, {event.uid for event in events})

    print(f"Done. created={counts['created']} updated={counts['updated']} deleted={deleted}")
    return 0


def _read_ics(path: Path | None, url: str | None) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8-sig")
    if url is None:
        raise ValueError("Either --ics or --ics-url is required.")
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def _filter_window(events: list[IcsEvent], days_back: int, days_ahead: int) -> list[IcsEvent]:
    today = date.today()
    start = today - timedelta(days=days_back)
    end = today + timedelta(days=days_ahead)
    return [event for event in events if start <= _event_date(event.start) <= end]


def _event_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value
