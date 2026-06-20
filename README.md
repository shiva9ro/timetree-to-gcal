# TimeTree to Google Calendar

TimeTree の予定を ICS に書き出して、必要なら Google Calendar にコピーするための作業フォルダです。

TimeTree から ICS を作る部分は、非公式ツール [eoleedi/TimeTree-Exporter](https://github.com/eoleedi/TimeTree-exporter) を使います。

## 1. セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

インストール確認:

```powershell
.\.venv\Scripts\timetree-exporter.exe --help
```

## 2. TimeTreeからICSを作る

一番シンプルな実行:

```powershell
.\.venv\Scripts\timetree-exporter.exe -o .\timetree.ics
```

実行すると、TimeTree のメールアドレスとパスワードの入力、エクスポートするカレンダーの選択を求められます。
成功すると、このフォルダに `timetree.ics` ができます。

メールアドレスだけ先に指定する場合:

```powershell
.\.venv\Scripts\timetree-exporter.exe -e your-email@example.com -o .\timetree.ics
```

カレンダーコードが分かっている場合:

```powershell
.\.venv\Scripts\timetree-exporter.exe -e your-email@example.com -c calendar_code -o .\timetree.ics
```

カレンダーコードは、TimeTree Web版のカレンダーページURLや、`-c` なしで実行したときの選択画面で確認します。

## 3. パスワードを毎回入力したくない場合

PowerShell の環境変数で渡せます。

```powershell
$env:TIMETREE_EMAIL="your-email@example.com"
$env:TIMETREE_PASSWORD="your-password"
.\.venv\Scripts\timetree-exporter.exe -o .\timetree.ics
```

ただし、まずは手入力で動作確認するのがおすすめです。パスワードをコマンド引数に直接書くより安全です。

## 4. 作ったICSを確認する

Google Calendar に書き込まず、ICS が読めるかだけ確認します。

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter sync --ics .\timetree.ics --calendar-id primary --dry-run
```

## 5. Google Calendarへコピーする

Google Calendar API の `credentials.json` をこのフォルダに置いたあと実行します。

```powershell
.\.venv\Scripts\python.exe -m time_tree_exporter sync --ics .\timetree.ics --calendar-id primary
```

初回だけブラウザで Google 認証が開き、認証後に `token.json` が作られます。

## 6. WindowsでTimeTree取得からGoogle同期まで一発で動かす

TimeTreeのメールアドレスとパスワードを `.env` に入れます。

```powershell
Copy-Item .\.env.example .\.env
notepad .\.env
```

`.env` の中身:

```text
TIMETREE_EMAIL=your-email@example.com
TIMETREE_PASSWORD=your-password
TIMETREE_CALENDAR_CODE=your-calendar-code
```

`.env` は `.gitignore` で除外しています。

PowerShellの環境変数で渡すこともできます。

```powershell
$env:TIMETREE_EMAIL="your-email@example.com"
$env:TIMETREE_PASSWORD="your-password"
```

まずはGoogleへ書き込まずに確認します。

```powershell
.\sync-timetree.ps1 -CalendarId primary -DryRun
```

問題なければ同期します。

```powershell
.\sync-timetree.ps1 -CalendarId primary
```

カレンダーコードをコマンドで指定する場合:

```powershell
.\sync-timetree.ps1 -CalendarId primary -CalendarCode "your_timetree_calendar_code"
```

同期範囲を変える場合:

```powershell
.\sync-timetree.ps1 -CalendarId primary -DaysBack 1 -DaysAhead 60
```

TimeTreeから消えた予定をGoogle側からも消したい場合:

```powershell
.\sync-timetree.ps1 -CalendarId primary -DeleteMissing
```

`-DeleteMissing` は、このツールがGoogle Calendar APIで作った予定だけを対象にします。
手動ICSインポートで入れた予定には同期用IDが付いていないため、削除対象になりません。

## 差分同期

`sync-timetree.ps1` は、通常はTimeTreeの差分APIを使います。

- 初回だけ全イベントを取得し、`timetree-cache.json` に保存します。
- 最大 `updated_at + 1` を `sync-state.json` に保存します。
- 2回目以降は `/events?since=...` で変更分だけ取得します。
- 変更がなければ、TimeTreeのイベント取得は1リクエストで終了します。
- `deactivated_at` が付いた変更イベントは、Google Calendarからも削除します。
- Google Calendarへは、変更された予定だけを作成・更新します。
- 日付が変わったときは、新しく同期範囲へ入った予定だけをGoogle Calendarへ追加します。
- TimeTreeの変更も同期範囲の変化もなければ、Google Calendar APIの予定操作は0件です。
- TimeTreeのラベル名をキャッシュし、Googleの予定名を `【ラベル名】予定タイトル` にします。

キャッシュを作り直して全件確認したい場合:

```powershell
.\sync-timetree.ps1 -CalendarId "GoogleカレンダーID" -FullRefresh
```

Alexaが朝07:45、夜20:45に読み上げる場合、Windowsタスクスケジューラやcronでは07:35と20:35の同期を推奨します。

## Raspberry Pi / Linux

Linuxでは `.env` に `GOOGLE_CALENDAR_ID` も設定し、次を実行します。

```bash
./sync-timetree.sh
```

systemdのユーザーサービス例は `deploy/systemd` にあります。`%h/timetree-to-gcal` に配置する前提です。

## メモ

- `timetree-exporter` は TimeTree 公式ではない非公式ツールです。TimeTree側の仕様変更で動かなくなる可能性があります。
- Google Calendar に取り込むときは、まず専用カレンダーを作って試すのがおすすめです。失敗してもそのカレンダーを消せます。
- `credentials.json`、`token.json`、`.ics` は `.gitignore` で除外しています。
