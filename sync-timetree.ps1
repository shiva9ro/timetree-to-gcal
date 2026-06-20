param(
    [string]$CalendarId = "primary",
    [string]$CalendarCode = "",
    [int]$DaysBack = 1,
    [int]$DaysAhead = 30,
    [switch]$DryRun,
    [switch]$DeleteMissing,
    [switch]$FullRefresh
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$Output = Join-Path $ProjectDir "timetree.ics"
$EnvFile = Join-Path $ProjectDir ".env"

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }

        $name, $value = $line -split "=", 2
        if ($name -and ($null -ne $value)) {
            $name = $name.Trim()
            $value = $value.Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

if (-not (Test-Path $Python)) {
    throw "Python venv not found: $Python"
}

if (-not $env:TIMETREE_EMAIL) {
    throw "TIMETREE_EMAIL is not set."
}

if (-not $env:TIMETREE_PASSWORD) {
    throw "TIMETREE_PASSWORD is not set."
}

if (-not $CalendarCode -and $env:TIMETREE_CALENDAR_CODE) {
    $CalendarCode = $env:TIMETREE_CALENDAR_CODE
}

if (-not $CalendarCode) {
    throw "Calendar code is not set. Add TIMETREE_CALENDAR_CODE to .env or pass -CalendarCode."
}

$argsList = @(
    "-m", "time_tree_exporter", "sync-timetree",
    "--calendar-id", $CalendarId,
    "--email", $env:TIMETREE_EMAIL,
    "--output", $Output,
    "--days-back", $DaysBack,
    "--days-ahead", $DaysAhead
)

if ($CalendarCode) {
    $argsList += @("--calendar-code", $CalendarCode)
}

if ($DryRun) {
    $argsList += "--dry-run"
}

if ($DeleteMissing) {
    $argsList += "--delete-missing"
}

if ($FullRefresh) {
    $argsList += "--full-refresh"
}

& $Python @argsList
