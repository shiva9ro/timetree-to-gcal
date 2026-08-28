# TimeTree to Google Calendar

English | [日本語](README.ja.md)

An unofficial Python tool that incrementally syncs TimeTree events to Google Calendar.
It is designed to make TimeTree schedules available to Alexa routines through Google Calendar.

## Features

- Fetch all TimeTree events on the first run
- Fetch only changes on later runs using a `since` cursor
- Create, update, and delete Google Calendar events
- Prefix titles with their TimeTree label, such as `【School】Parent observation day`
- Add unchanged events when they enter the configured sync window
- Create TimeTree events from JSON with dry-run and duplicate checking
- Sync ICS files, generate ICS from CSV, and sanitize ICS for Google Calendar
- Run periodically on Raspberry Pi with a systemd user timer

## Requirements

- Python 3.11 or later
- A Google Calendar API Desktop OAuth client
- A TimeTree email address, password, and calendar code

## Setup

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .\.env.example .\.env
notepad .\.env
```

### Linux / Raspberry Pi

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env credentials.json token.json
```

## Configuration

Set the following values in `.env`:

```text
TIMETREE_EMAIL=your-email@example.com
TIMETREE_PASSWORD=your-password
TIMETREE_CALENDAR_CODE=your-calendar-code
GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
```

Create a Desktop OAuth client in Google Cloud and save it as `credentials.json`.
The first run opens a browser for authorization and then saves the credentials to `token.json`.

These files are excluded from Git.

## Sync TimeTree to Google Calendar

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter sync-timetree
```

Linux / Raspberry Pi:

```bash
.venv/bin/python -m time_tree_exporter sync-timetree
```

Discard the local cursor and fetch all events again:

```text
<virtual-environment-python> -m time_tree_exporter sync-timetree --full-refresh
```

Automated jobs call the Python executable inside the virtual environment directly. Activating the
environment interactively is not required.

## How delta sync works

- The first run saves TimeTree events to `timetree-cache.json`.
- The next cursor, calculated as the largest `updated_at + 1`, is saved to `sync-state.json`.
- Later runs request changes from `/events?since=...`.
- Events with `deactivated_at` are removed from Google Calendar.
- When the date changes, unchanged events entering the sync window are added.
- With no changes, TimeTree receives one request and Google Calendar receives no event operations.

## Create TimeTree events from JSON

This is a separate workflow from calendar synchronization. It accepts event data normalized into a
common JSON format, allows a person to review it, and supports a dry run before writing to TimeTree.
See [`examples/timetree-events.example.json`](examples/timetree-events.example.json) for the input
format.

```text
Unstructured schedule notice
  -> normalize to common JSON
  -> review manually
  -> dry-run with create-timetree-event
  -> add --commit to create the events
```

The following command resolves the calendar and labels and prints the request without creating an
event:

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter create-timetree-event --input examples\timetree-events.example.json
```

Set `label` to a TimeTree label name, or use `null` to omit an explicit label. Add `--commit` only
when the reviewed events are ready to be created:

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter create-timetree-event --input examples\timetree-events.example.json --commit
```

An example of schedule-selection rules is available in
[`docs/schedule-import-rules.example.md`](docs/schedule-import-rules.example.md). Keep personal rules
and input data in the Git-ignored `data/` directory.

## Other commands

Run `<virtual-environment-python> -m time_tree_exporter --help` to see all options.

| Command | Purpose |
| --- | --- |
| `sync-timetree` | Incrementally sync TimeTree events to Google Calendar |
| `create-timetree-event` | Validate JSON and optionally create TimeTree events |
| `sync` | Sync events from an ICS file to Google Calendar |
| `make-ics` | Generate an ICS file from CSV |
| `sanitize-ics` | Create a Google Calendar-friendly ICS file |
| `delete-ics-events` | Delete Google Calendar events whose iCalUIDs occur in an ICS file |

## Schedule with systemd

The included user timer runs at 07:35 and 20:35, ten minutes before the example Alexa routines at
07:45 and 20:45. The service expects this repository at `~/timetree-to-gcal`.

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/timetree-to-gcal.service ~/.config/systemd/user/
cp deploy/systemd/timetree-to-gcal.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now timetree-to-gcal.timer
```

Check the timer and its next run:

```bash
systemctl --user status timetree-to-gcal.timer
systemctl --user list-timers timetree-to-gcal.timer
```

Run a sync manually and inspect recent logs:

```bash
systemctl --user start timetree-to-gcal.service
journalctl --user -u timetree-to-gcal.service -n 50 --no-pager
```

## Security

Do not add the following files to Git:

```text
.env
credentials.json
token.json
sync-state.json
timetree-cache.json
timetree-labels.json
*.ics
raw-timetree*/
data/
```

## Disclaimer

This project is not affiliated with TimeTree. It uses an internal TimeTree API and may stop working
when that API changes. Avoid frequent polling.

## Related articles

- [TimeTreeの予定をGoogleカレンダーへ差分同期するツールを作った (Qiita, Japanese)](https://qiita.com/shiva9ro/items/456f4450854b799683f7)

## License

[MIT License](LICENSE)
