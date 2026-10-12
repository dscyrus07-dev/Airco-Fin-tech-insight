# Slice 2A + 2B - run everything (Docker, Python 3.11). Never hides a failure: every stage gets [PASS]/[WARN]/[FAIL] and a real exit code.
# Usage (from the project root):  powershell -ExecutionPolicy Bypass -File .\docs\slice2\run_slice2b.ps1
# Options: -PerBank 60 (files per bank folder; 0 = every file)   -Workers 4   -TestsOnly (skip the corpus benchmark)
param([int]$PerBank = 60, [int]$Workers = 4, [switch]$TestsOnly)

$ErrorActionPreference = 'Continue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
$out  = Join-Path $root 'docs\slice2\out'
$logs = Join-Path $out 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$image   = 'airco-backend-slice1'
$samples = Join-Path $root 'New Dataset\Ready to Use PDF'
$status  = New-Object System.Collections.ArrayList
$runStart = Get-Date

function D($dockerArgs) { docker run --rm -v "${root}\backend:/app" --tmpfs /app/data -w /app @dockerArgs }

function Step($name, [scriptblock]$body, [scriptblock]$judge = $null) {
    $t0 = Get-Date
    $log = Join-Path $logs "$name.log"
    Write-Host "=== $name ===" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $body 2>&1 | Tee-Object -FilePath $log | Out-Host
    $code = $LASTEXITCODE
    $text = if (Test-Path $log) { Get-Content $log -Raw } else { '' }
    $verdict = if ($code -eq 0) { 'PASS' } else { 'FAIL' }
    $note = ''
    if ($judge) { $r = & $judge $code $text; if ($r) { $verdict = $r[0]; $note = $r[1] } }
    $color = @{ PASS = 'Green'; WARN = 'Yellow'; FAIL = 'Red' }[$verdict]
    Write-Host ("[{0}] {1} (exit {2}) {3}" -f $verdict, $name, $code, $note) -ForegroundColor $color
    [void]$status.Add([pscustomobject]@{ verdict = $verdict; step = $name; exit_code = $code; seconds = [int]((Get-Date) - $t0).TotalSeconds; note = $note })
}

# Test ids that fail in a log: lines "FAILED tests/..." or "ERROR tests/..." (NOT log lines that merely start with ERROR).
function FailedIds($text) {
    [regex]::Matches($text, '(?m)^(?:FAILED|ERROR) (tests/\S+)') | ForEach-Object { $_.Groups[1].Value.Trim() } | Sort-Object -Unique
}
$known = @(Get-Content (Join-Path $PSScriptRoot 'known_failures.txt') | Where-Object { $_ -and -not $_.StartsWith('#') } | ForEach-Object { $_.Trim() })

# A failure outside known_failures.txt is NEW (ours until proven otherwise). Known failures that now pass are reported, not hidden.
function GuardJudge($c, $t) {
    $now = FailedIds $t
    $new = @($now | Where-Object { $known -notcontains $_ })
    $fixed = @($known | Where-Object { $_ -like 'tests/*' -and $now -notcontains $_ -and ($t -match [regex]::Escape(($_ -split '::')[0])) })
    $note = "failing: $($now.Count); known: $(@($now | Where-Object { $known -contains $_ }).Count); NEW: $($new.Count)"
    if ($new.Count -gt 0) { return @('FAIL', "$note :: " + ($new -join ' | ')) }
    if ($c -ne 0 -and $now.Count -eq 0) { return @('FAIL', "pytest exit $c but no failing test ids parsed - read the log") }
    return @('PASS', $note)
}

Step '00_git_state' {
    git branch --show-current
    git status --short | Measure-Object | ForEach-Object { "status lines: $($_.Count)" }
    $global:LASTEXITCODE = 0
}
Step '01_build_image' { docker build -t $image .\backend }
Step '02_new_tests' { D @($image, 'sh', '-c', 'pip install -q pytest 2>&1 | tail -1; python -m pytest tests/statement_engine tests/verification -v --tb=short -rs') } {
    param($c, $t)
    if ($c -ne 0) { return @('FAIL', 'a Slice 1 / Slice 2 test failed: read the log') }
    $skipped = [regex]::Match($t, '(\d+) skipped').Groups[1].Value
    if ($skipped) { return @('WARN', "$skipped tests were skipped (a skipped test is not a pass)") }
    $p = [regex]::Match($t, '(\d+) passed').Groups[1].Value
    return @('PASS', "$p passed")
}
Step '03_existing_suite_guard' { D @($image, 'sh', '-c', 'pip install -q pytest pytest-asyncio 2>&1 | tail -1; python -m pytest tests --tb=short -q -p no:cacheprovider --continue-on-collection-errors --ignore=tests/verification --ignore=tests/statement_engine --ignore=tests/golden -rfE') } { param($c, $t) GuardJudge $c $t }
Step '04_golden_guard' {
    D @('-v', "${root}\samples:/golden_samples:ro", '-e', 'GOLDEN_SAMPLES_DIR=/golden_samples', $image, 'sh', '-c', 'pip install -q pytest pytest-asyncio 2>&1 | tail -1; python -m pytest tests/golden --tb=short -q -p no:cacheprovider -rfE')
} { param($c, $t) GuardJudge $c $t }

if (-not $TestsOnly) {
Step '05_detection_benchmark' {
    D @('-v', "${samples}:/samples:ro", '-v', "${out}:/out", $image,
        'python', '-m', 'scripts.detection_benchmark', '--samples-dir', '/samples', '--out-dir', '/out',
        '--per-bank', "$PerBank", '--workers', "$Workers")
} {
    param($c, $t)
    if ($c -ne 0) { return }
    $sum = Join-Path $out 'detection_summary.md'
    if (-not (Test-Path $sum)) { return @('FAIL', 'detection_summary.md was not produced') }
    $s = Get-Content $sum -Raw
    if ($s -match '## Errors') { return @('FAIL', 'some files raised errors: see detection_summary.md') }
    $hi = [regex]::Match($s, 'HIGH or VERY_HIGH: (\d+)').Groups[1].Value
    if ($hi -and [int]$hi -gt 0) { return @('WARN', "$hi confident disagreements with the folder label: review detection_disagreements.csv (each is a misplaced file or a detector bug)") }
    return @('PASS', 'no confident disagreements')
}
}

$fail = @($status | Where-Object verdict -eq 'FAIL').Count
$warn = @($status | Where-Object verdict -eq 'WARN').Count
$lines = @("Slice 2A/2B run started $runStart, finished $(Get-Date)", '')
foreach ($s in $status) { $lines += ("[{0}] {1}  (exit {2}, {3}s) {4}" -f $s.verdict, $s.step, $s.exit_code, $s.seconds, $s.note) }
$overall = if ($fail -gt 0) { 'FAIL' } elseif ($warn -gt 0) { 'WARN' } else { 'PASS' }
$lines += ''
$lines += "OVERALL: $overall  ($fail failed, $warn warnings, $(@($status | Where-Object verdict -eq 'PASS').Count) passed)"
$lines | Set-Content -Path (Join-Path $out 'RUN_STATUS.txt') -Encoding UTF8
$status | ConvertTo-Json | Set-Content -Path (Join-Path $out 'RUN_STATUS.json') -Encoding UTF8
$lines | ForEach-Object { Write-Host $_ }
Write-Host "Read docs\slice2\out\RUN_STATUS.txt, detection_summary.md, detection_disagreements.csv"
if ($fail -gt 0) { exit 1 } else { exit 0 }
