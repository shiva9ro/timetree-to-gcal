# TimeTree to Google Calendar

TimeTreeの予定を差分取得し、Google Calendarへ同期する非公式ツールです。
Alexaの定型アクションから当日・翌日の予定を読み上げる用途を想定しています。

## Features

- 初回のみTimeTreeのイベントを全件取得
- 2回目以降は `since` カーソルによる差分取得
- Google Calendarへの新規作成・変更・削除
- TimeTreeのラベル名を `【ラベル名】予定タイトル` として反映
- ローカルキャッシュによる同期範囲への予定追加
- Windows PowerShellとLinux/Raspberry Piに対応

## Requirements

- Python 3.11以上
- Google Calendar APIのDesktop OAuthクライアント
- TimeTreeのメールアドレス、パスワード、カレンダーコード

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

`.env`:

```text
TIMETREE_EMAIL=your-email@example.com
TIMETREE_PASSWORD=your-password
TIMETREE_CALENDAR_CODE=your-calendar-code
GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
```

Google Cloudで作成したOAuthクライアントを `credentials.json` として配置します。
初回認証後は `token.json` が作成されます。

これらのファイルはGit管理対象外です。

## Run

### Windows

```powershell
.\sync-timetree.ps1 -CalendarId "GoogleカレンダーID"
```

`.env` に `GOOGLE_CALENDAR_ID` があれば、Python CLIを直接実行することもできます。

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter sync-timetree
```

### Linux / Raspberry Pi

```bash
.venv/bin/python -m time_tree_exporter sync-timetree
```

キャッシュを破棄して全件取得し直す場合:

```powershell
.\sync-timetree.ps1 -CalendarId "GoogleカレンダーID" -FullRefresh
```

```bash
.venv/bin/python -m time_tree_exporter sync-timetree --full-refresh
```

## Delta Sync

- 初回イベントを `timetree-cache.json` に保存します。
- 最大 `updated_at + 1` を `sync-state.json` に保存します。
- 以後は `/events?since=...` から変更分だけ取得します。
- `deactivated_at` が設定された予定はGoogle Calendarから削除します。
- 日付が変わると、新しく同期範囲へ入った予定だけをGoogle Calendarへ追加します。
- 変更がなければ、TimeTreeは1リクエスト、Googleの予定操作は0件です。

## Scheduling

Alexaが07:45と20:45に読み上げる場合、07:35と20:35の同期を想定しています。

systemdのユーザーサービスとタイマー例は `deploy/systemd` にあります。
配置先は `%h/timetree-to-gcal` です。

## Security

次のファイルはGitへ追加しないでください。

```text
.env
credentials.json
token.json
sync-state.json
timetree-cache.json
timetree-labels.json
```

## Disclaimer

このプロジェクトはTimeTree公式ではありません。TimeTreeの内部APIを利用しているため、
仕様変更によって動作しなくなる可能性があります。短い間隔でのポーリングは避けてください。

## Acknowledgements

内部APIの調査と初期ICS出力の検証では、MIT Licenseの
[eoleedi/TimeTree-Exporter](https://github.com/eoleedi/TimeTree-exporter) を参考にしました。
現在の通常同期は同パッケージを依存関係として使用せず、
このプロジェクト内の差分同期クライアントで動作します。
