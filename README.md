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

WindowsとLinuxは、どちらも仮想環境内のPythonから同じモジュールと
サブコマンドを実行します。仮想環境の有効化は不要です。

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter sync-timetree
```

Linux / Raspberry Pi:

```bash
.venv/bin/python -m time_tree_exporter sync-timetree
```

キャッシュを破棄して全件取得し直す場合:

```text
<仮想環境のPython> -m time_tree_exporter sync-timetree --full-refresh
```

自動実行では仮想環境を対話的に有効化せず、仮想環境内のPythonを直接指定します。
`deploy/systemd/timetree-to-gcal.service` も同じPythonモジュールを実行します。

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

## TimeTreeへの予定登録CLI（同期とは別機能）

登録用JSONは月ごとに `data/imports/YYYY-MM/` へ保存します。
対象者や予定選別の個人ルールは `data/schedule-import-rules.md` に記録します。
Git管理できる一般例は `docs/schedule-import-rules.example.md` にあります。
次のコマンドはカレンダーとラベルを読み取って送信内容を表示するだけで、予定は作成しません。

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter create-timetree-event --input examples\timetree-events.example.json
```

JSONの `label` にはTimeTree上のラベル名を指定します。`null` ならラベルを明示しません。
実際に作成するときだけ末尾に `--commit` を付けます。

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter create-timetree-event --input examples\timetree-events.example.json --commit
```

## Acknowledgements

内部APIの調査と初期ICS出力の検証では、MIT Licenseの
[eoleedi/TimeTree-Exporter](https://github.com/eoleedi/TimeTree-exporter) を参考にしました。
現在の通常同期は同パッケージを依存関係として使用せず、
このプロジェクト内の差分同期クライアントで動作します。
