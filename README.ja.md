# TimeTree to Google Calendar

[English](README.md) | 日本語

TimeTreeの予定を差分取得し、Google Calendarへ同期する非公式のPythonツールです。
Google Calendarを経由し、Alexaの定型アクションからTimeTreeの予定を読み上げる用途を想定しています。

開発の背景や構成については
[Qiitaの記事](https://qiita.com/shiva9ro/items/456f4450854b799683f7)も参照してください。

## 主な機能

- 初回のみTimeTreeのイベントを全件取得
- 2回目以降は`since`カーソルによる差分取得
- Google Calendarへの予定の新規作成・変更・削除
- TimeTreeのラベル名を`【ラベル名】予定タイトル`として反映
- 日付が変わり同期範囲へ入った予定をローカルキャッシュから追加
- JSONからTimeTreeへ予定を登録するCLI（dry-run・重複確認対応）
- ICS同期、CSVからのICS生成、Google Calendar向けICS整形
- Raspberry Piとsystemdユーザータイマーによる定期実行

## 必要なもの

- Python 3.11以上
- Google Calendar APIのDesktop OAuthクライアント
- TimeTreeのメールアドレス、パスワード、カレンダーコード

## セットアップ

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

## 設定

`.env`に次の値を設定します。

```text
TIMETREE_EMAIL=your-email@example.com
TIMETREE_PASSWORD=your-password
TIMETREE_CALENDAR_CODE=your-calendar-code
GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
```

Google CloudでDesktop OAuthクライアントを作成し、`credentials.json`として配置します。
初回実行時にブラウザで認証すると、`token.json`が保存されます。

これらのファイルはGit管理対象外です。

## TimeTreeからGoogle Calendarへ同期

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter sync-timetree
```

Linux / Raspberry Pi:

```bash
.venv/bin/python -m time_tree_exporter sync-timetree
```

ローカルのカーソルを破棄して全件取得し直す場合:

```text
<仮想環境のPython> -m time_tree_exporter sync-timetree --full-refresh
```

自動実行では仮想環境を対話的に有効化せず、仮想環境内のPythonを直接指定します。

## 差分同期の仕組み

- 初回イベントを`timetree-cache.json`に保存します。
- 最大の`updated_at + 1`を次のカーソルとして`sync-state.json`に保存します。
- 2回目以降は`/events?since=...`から変更分だけ取得します。
- `deactivated_at`が設定された予定はGoogle Calendarから削除します。
- 日付が変わると、新しく同期範囲へ入った予定を追加します。
- 変更がなければ、TimeTreeは1リクエスト、Google Calendarの予定操作は0件です。

## JSONからTimeTreeへ予定を登録

カレンダー同期とは別の機能です。連絡文などを共通JSONへ整形し、人が確認してから
TimeTreeへ登録するワークフローを想定しています。入力形式は
[`examples/timetree-events.example.json`](examples/timetree-events.example.json)を参照してください。

```text
自由形式の連絡文
  → 共通JSONへ整形
  → 人が内容を確認
  → create-timetree-eventでdry-run
  → --commitを付けてTimeTreeへ登録
```

次のコマンドはカレンダーとラベルを読み取り、送信内容を表示するだけで予定は作成しません。

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter create-timetree-event --input examples\timetree-events.example.json
```

JSONの`label`にはTimeTree上のラベル名を指定します。`null`ならラベルを明示しません。
確認済みの予定を作成するときだけ`--commit`を付けます。

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter create-timetree-event --input examples\timetree-events.example.json --commit
```

予定選別ルールの一般例は
[`docs/schedule-import-rules.example.md`](docs/schedule-import-rules.example.md)にあります。
個人用のルールや入力データはGit管理対象外の`data/`へ保存します。

## その他のコマンド

すべてのオプションは`<仮想環境のPython> -m time_tree_exporter --help`で確認できます。

| コマンド | 内容 |
| --- | --- |
| `sync-timetree` | TimeTreeから差分取得してGoogle Calendarへ同期 |
| `create-timetree-event` | JSONを検証し、必要に応じてTimeTreeへ予定を登録 |
| `sync` | ICSの予定をGoogle Calendarへ同期 |
| `make-ics` | CSVからICSファイルを生成 |
| `sanitize-ics` | Google CalendarへインポートしやすいICSへ整形 |
| `delete-ics-events` | ICS内のiCalUIDと一致する予定をGoogle Calendarから削除 |

## systemdによる定期実行

同梱のユーザータイマーは07:35と20:35に同期します。これはAlexaの定型アクションで
07:45に当日、20:45に翌日の予定を読み上げる構成例に合わせた時刻です。
サービスはリポジトリが`~/timetree-to-gcal`にあることを前提としています。

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/timetree-to-gcal.service ~/.config/systemd/user/
cp deploy/systemd/timetree-to-gcal.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now timetree-to-gcal.timer
```

登録状態と次回実行時刻を確認します。

```bash
systemctl --user status timetree-to-gcal.timer
systemctl --user list-timers timetree-to-gcal.timer
```

同期を手動実行し、直近のログを確認する場合:

```bash
systemctl --user start timetree-to-gcal.service
journalctl --user -u timetree-to-gcal.service -n 50 --no-pager
```

## セキュリティ

次のファイルはGitへ追加しないでください。

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

## 注意事項

このプロジェクトはTimeTree公式ではありません。TimeTreeの内部APIを利用しているため、
仕様変更によって動作しなくなる可能性があります。短い間隔での実行は避けてください。

## ライセンス

[MIT License](LICENSE)
