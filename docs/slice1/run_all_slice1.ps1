# Slice 1 - run everything unattended (Docker, Python 3.11). Safe to leave running overnight.
# Never modifies the dataset (mounted read-only), never touches git, never stops on a failing step,
# but NEVER hides a failure: every stage gets an explicit [PASS] / [WARN] / [FAIL] with its real exit code.
# Usage (PowerShell, from the project root):
#   powershell -ExecutionPolicy Bypass -File .\docs\slice1\run_all_slice1.ps1
# Options: -SkipStack (skip the live UI/API end-to-end part)   -TestsOnly (stop after the golden stage: ~2 minutes)   -PerBank 25
# Test tooling: pytest is NOT in requirements.txt, so it is pip-installed inside each throw-away container
# (nothing is added to the project, the image or requirements.txt).
param([switch]$SkipStack, [switch]$TestsOnly, [int]$PerBank = 25)

$ErrorActionPreference = 'Continue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
$out  = Join-Path $root 'docs\slice1\out'
$logs = Join-Path $out 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$image   = 'airco-backend-slice1'
$samples = Join-Path $root 'New Dataset\Ready to Use PDF'
$ref     = Join-Path $root 'New Dataset\_validation_by_claude'
$status  = New-Object System.Collections.ArrayList
$runStart = Get-Date

# --tmpfs /app/data: the existing parsers write parser_metrics.json / unsupported_formats/ under backend/data;
# keep run artefacts out of the repo working tree (run 1 left backend/data/parser_metrics.json and backend/data/unsupported_formats/ behind).
function D($dockerArgs) { docker run --rm -v "${root}\backend:/app" --tmpfs /app/data -w /app @dockerArgs }

# $judge receives (exitCode, logText) and returns 'PASS' | 'WARN' | 'FAIL' plus a note.
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

Step '00_git_state' {
    git branch --show-current
    git status --short | Measure-Object | ForEach-Object { "status lines: $($_.Count)" }
    git diff --ignore-space-at-eol --stat
    $global:LASTEXITCODE = 0
}
Step '01_build_image' { docker build -t $image .\backend }
Step '02_environment' {
    D @($image, 'python', '-V')
    D @($image, 'python', '-m', 'pip', 'list', '--format=freeze')
    docker image inspect $image --format 'image id: {{.Id}} created: {{.Created}}'
    $global:LASTEXITCODE = 0
} { param($c, $t) if ($t -notmatch 'Python 3\.11') { @('FAIL', 'not Python 3.11') } }
Step '03_verification_tests' { D @($image, 'sh', '-c', 'pip install -q pytest 2>&1 | tail -1; python -m pytest tests/verification -v --tb=short') } {
    param($c, $t) if ($c -eq 0 -and $t -notmatch '22 passed') { @('WARN', 'expected 22 passed') }
}
Step '04_existing_suite' { D @($image, 'sh', '-c', 'pip install -q pytest pytest-asyncio 2>&1 | tail -1; python -m pytest tests --tb=short -q -p no:cacheprovider --continue-on-collection-errors --ignore=tests/verification --ignore=tests/golden') } {
    param($c, $t) if ($c -ne 0) { @('FAIL', 'see log; classify each failure PRE-EXISTING / OURS / ENVIRONMENT / UNRELATED') }
}
Step '05_golden' {
    D @('-v', "${root}\samples:/golden_samples:ro", '-e', 'GOLDEN_SAMPLES_DIR=/golden_samples', $image, 'sh', '-c', 'pip install -q pytest pytest-asyncio 2>&1 | tail -1; python -m pytest tests/golden -v --tb=short -rsfE')
} {
    param($c, $t)
    if ($c -eq 5 -or $t -match 'no tests ran') { return @('WARN', 'no golden tests ran') }
    if ($c -eq 0 -and $t -match 'skipped') { return @('WARN', 'some golden tests were SKIPPED (samples missing?) - not a pass') }
}
# ---- A/B: do the failing tests also fail WITHOUT our changes? --------------------------------------
# Same tests, same image, but on a throw-away copy of backend/ where base_processor.py and
# frontend_result_builder.py are replaced by their committed versions (docs/slice1/pristine, LF-only copies
# of HEAD) and the verification package is removed. A failure present in both runs is PRE-EXISTING;
# a failure only in the first run is OURS.
function FailedSet($text) {
    [regex]::Matches($text, '(?m)^(?:FAILED|ERROR) (tests/\S+)') | ForEach-Object { $_.Groups[1].Value.Trim() } | Sort-Object -Unique
}
function AbJudge($mainLog, $c, $t) {
    $main = FailedSet (Get-Content (Join-Path $logs $mainLog) -Raw)
    $pris = FailedSet $t
    $ours = @($main | Where-Object { $pris -notcontains $_ })
    $pre  = @($main | Where-Object { $pris -contains $_ })
    $fixed = @($pris | Where-Object { $main -notcontains $_ })
    $note = "pre-existing (fail with and without our changes): $($pre.Count); OURS (fail only with our changes): $($ours.Count); fixed by our changes: $($fixed.Count)"
    if ($ours.Count -gt 0) { return @('FAIL', "$note :: " + ($ours -join ' | ')) }
    return @('PASS', $note)
}
$abCopy = 'cp -r /src/. /work/ && cp /pristine/base_processor.py /work/app/services/banks/_shared/base_processor.py && cp /pristine/frontend_result_builder.py /work/app/services/frontend_result_builder.py && rm -rf /work/app/services/verification && cd /work && pip install -q pytest pytest-asyncio 2>&1 | tail -1;'
Step '04b_existing_suite_WITHOUT_our_changes' {
    docker run --rm -v "${root}\backend:/src:ro" -v "${root}\docs\slice1\pristine:/pristine:ro" --tmpfs /work/data -w /work $image sh -c ($abCopy + ' python -m pytest tests --tb=line -q -p no:cacheprovider --continue-on-collection-errors --ignore=tests/verification --ignore=tests/golden')
} { param($c, $t) AbJudge '04_existing_suite.log' $c $t }
Step '05b_golden_WITHOUT_our_changes' {
    docker run --rm -v "${root}\backend:/src:ro" -v "${root}\docs\slice1\pristine:/pristine:ro" -v "${root}\samples:/golden_samples:ro" -e GOLDEN_SAMPLES_DIR=/golden_samples --tmpfs /work/data -w /work $image sh -c ($abCopy + ' python -m pytest tests/golden --tb=line -q -p no:cacheprovider')
} { param($c, $t) AbJudge '05_golden.log' $c $t }

if (-not $TestsOnly) {
Step '06_corpus_baseline' {
    D @('-v', "${samples}:/samples:ro", '-v', "${ref}:/ref:ro", '-v', "${out}:/out", $image,
        'python', '-m', 'scripts.baseline_run', '--samples-dir', '/samples', '--out-dir', '/out',
        '--per-bank', "$PerBank", '--exclude-csv', '/ref/MOVE_PLAN_not_executed.csv')
} {
    param($c, $t)
    if ($c -ne 0) { return }
    $sum = Join-Path $out 'baseline_summary.md'
    if (-not (Test-Path $sum)) { return @('FAIL', 'baseline_summary.md was not produced') }
    $s = Get-Content $sum -Raw
    if ($t -match 'time budget reached') { return @('WARN', 'PARTIAL: time budget reached, re-run to resume') }
    $sec = [regex]::Match($s, '(?s)## What happened to each PDF(.*?)##').Groups[1].Value
    $notParsed = [regex]::Matches($sec, '(?m)^- (?!parsed:)[^:\n]+: (\d+)') | ForEach-Object { [int]$_.Groups[1].Value } | Measure-Object -Sum
    if ($notParsed.Sum -gt 0) { return @('WARN', "COMPLETE, but $($notParsed.Sum) PDFs could not be parsed (wrong-bank / scanned / no table) - see needs_manual_review.csv") }
}

}

if (-not $SkipStack -and -not $TestsOnly) {
    $compose = @('compose', '-f', 'infra/docker/docker-compose.yml', '-f', 'infra/docker/docker-compose.local.yml', '--env-file', 'local.env')
    Step '07_stack_rebuild_backend' { docker @compose up -d --build backend }
    Step '08_stack_health' {
        $ok = $false
        for ($i = 0; $i -lt 40 -and -not $ok; $i++) {
            try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/health' -TimeoutSec 3; if ($r.StatusCode -eq 200) { $ok = $true; 'backend healthy' } } catch { Start-Sleep 3 }
        }
        if (-not $ok) { 'backend NOT healthy after ~2 minutes'; $global:LASTEXITCODE = 1 } else { $global:LASTEXITCODE = 0 }
    }
    $i = 0
    foreach ($b in @(@('HDFC Bank', 'hdfc'), @('ICICI Bank', 'icici'), @('SBI', 'sbi'), @('Axis Bank', 'axis'), @('Kotak Mahindra Bank', 'kotak'))) {
        $pdfs = @(Get-ChildItem -LiteralPath (Join-Path $samples $b[0]) -Filter *.pdf -File -ErrorAction SilentlyContinue | Select-Object -First 2)
        if ($pdfs.Count -eq 0) {
            $i++
            [void]$status.Add([pscustomobject]@{ verdict = 'FAIL'; step = ("09_e2e_{0:D2}_{1}" -f $i, $b[1]); exit_code = -1; seconds = 0; note = "no PDFs found in folder '$($b[0])'" })
            Write-Host "[FAIL] E2E $($b[1]): no PDFs found" -ForegroundColor Red
            continue
        }
        foreach ($p in $pdfs) {
            $i++
            $folder = $b[0]; $bank = $b[1]; $n = $i; $pname = $p.Name
            Step ("09_e2e_{0:D2}_{1}" -f $n, $bank) {
                docker run --rm -v "${root}\backend:/app" -v "${samples}:/samples:ro" -v "${out}:/out" -w /app $image `
                    python scripts/e2e_smoke.py --api http://host.docker.internal:8000 `
                    --pdf "/samples/$folder/$pname" --bank $bank `
                    --out ("/out/e2e_{0:D2}_{1}.json" -f $n, $bank)
            } {
                param($c, $t)
                if ($c -ne 0) { $f = ([regex]::Matches($t, '(?m)^FAIL .*') | ForEach-Object { $_.Value }) -join ' | '; return @('FAIL', $f) }
            }
        }
    }
}

# ---- final, unambiguous status -------------------------------------------------------------
$fail = @($status | Where-Object verdict -eq 'FAIL').Count
$warn = @($status | Where-Object verdict -eq 'WARN').Count
$lines = @("Slice 1 run started $runStart, finished $(Get-Date)", '')
foreach ($s in $status) { $lines += ("[{0}] {1}  (exit {2}, {3}s) {4}" -f $s.verdict, $s.step, $s.exit_code, $s.seconds, $s.note) }
$overall = if ($fail -gt 0) { 'FAIL' } elseif ($warn -gt 0) { 'WARN' } else { 'PASS' }
$lines += ''
$lines += "OVERALL: $overall  ($fail failed, $warn warnings, $(@($status | Where-Object verdict -eq 'PASS').Count) passed)"
$lines | Set-Content -Path (Join-Path $out 'RUN_STATUS.txt') -Encoding UTF8
$status | ConvertTo-Json | Set-Content -Path (Join-Path $out 'RUN_STATUS.json') -Encoding UTF8
$lines | ForEach-Object { Write-Host $_ }
Write-Host "Read docs\slice1\out\RUN_STATUS.txt, baseline_summary.md, e2e_*.json and logs\*.log"
if ($fail -gt 0) { exit 1 } else { exit 0 }
