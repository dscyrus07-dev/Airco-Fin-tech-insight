param(
    [ValidateSet("full", "bootstrap", "deploy", "ssh", "status", "logs")]
    [string]$Action = "full",
    [Alias("Host")]
    [string]$TargetHost = "ec2-52-2-56-129.compute-1.amazonaws.com",
    [string]$User = "ubuntu",
    [string]$KeyPath = (Join-Path (Split-Path -Parent $PSScriptRoot) "ssl\Airco Fintech.pem"),
    [string]$RemoteProjectDir = "/home/ubuntu/airco-insights",
    [string]$RemoteArchive = "/tmp/airco-insights-ec2.tar.gz",
    [string]$RemoteScript = "/tmp/setup-aws-server.sh",
    [string]$LogsService = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SshTarget = "$User@$TargetHost"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$TempArchive = Join-Path ([System.IO.Path]::GetTempPath()) "airco-insights-ec2-$Timestamp.tar.gz"
$ServerScriptLocal = Join-Path $PSScriptRoot "setup-aws-server.sh"

function Write-Log {
    param([string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
    Write-Host "[setup-aws-local] $Message" -ForegroundColor $Color
}

function Require-Path {
    param([string]$PathToCheck, [string]$Label)
    if (-not (Test-Path $PathToCheck)) {
        throw "$Label not found: $PathToCheck"
    }
}

function Require-Command {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required command not found: $Name"
    }
}

function New-DeployArchive {
    Write-Log "Creating deployment archive..."
    & tar -czf $TempArchive `
        --exclude=.git `
        --exclude=.github `
        --exclude=.next `
        --exclude=node_modules `
        --exclude=__pycache__ `
        --exclude=.pytest_cache `
        --exclude=.mypy_cache `
        --exclude=.ruff_cache `
        --exclude=.venv `
        --exclude=venv `
        --exclude=dist `
        --exclude=build `
        --exclude=*.log `
        --exclude=frontend/.env.local `
        --exclude=frontend/.next `
        --exclude=frontend/node_modules `
        --exclude=backend/__pycache__ `
        --exclude=backend/.pytest_cache `
        -C $ProjectRoot .

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create deployment archive."
    }
}

function Upload-ScriptOnly {
    Write-Log "Uploading server script to EC2..."
    & scp -i $KeyPath $ServerScriptLocal "${SshTarget}:$RemoteScript"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upload server setup script to EC2."
    }
}

function Upload-Assets {
    Write-Log "Uploading archive and server script to EC2..."
    & scp -i $KeyPath $TempArchive "${SshTarget}:$RemoteArchive"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upload archive to EC2."
    }

    Upload-ScriptOnly
}

function Invoke-RemoteSetup {
    param([string]$RemoteAction)

    $escapedProjectDir = $RemoteProjectDir.Replace("'", "'\''")
    $escapedArchive = $RemoteArchive.Replace("'", "'\''")
    $escapedScript = $RemoteScript.Replace("'", "'\''")
    $escapedAction = $RemoteAction.Replace("'", "'\''")
    $remoteCommand = "chmod +x '$escapedScript' && bash '$escapedScript' --action '$escapedAction' --project-dir '$escapedProjectDir' --archive '$escapedArchive'"

    Write-Log "Running remote action '$RemoteAction'..."
    & ssh -i $KeyPath $SshTarget $remoteCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Remote setup action failed: $RemoteAction"
    }
}

function Open-SshShell {
    Write-Log "Opening SSH shell..."
    & ssh -i $KeyPath $SshTarget
}

function Show-Status {
    Invoke-RemoteSetup -RemoteAction "status"
}

function Show-Logs {
    $serviceArg = if ([string]::IsNullOrWhiteSpace($LogsService)) { "" } else { " --logs-service '$($LogsService.Replace("'", "'\''"))'" }
    $remoteCommand = "chmod +x '$RemoteScript' && bash '$RemoteScript' --action 'logs' --project-dir '$RemoteProjectDir' --archive '$RemoteArchive'$serviceArg"
    & ssh -i $KeyPath $SshTarget $remoteCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to fetch logs."
    }
}

Require-Path $KeyPath "SSH key"
Require-Path $ServerScriptLocal "Server setup script"
Require-Command "ssh"
Require-Command "scp"
Require-Command "tar"

Write-Log "Project root: $ProjectRoot"
Write-Log "Target host: $SshTarget"
Write-Log "Remote dir: $RemoteProjectDir"

try {
    switch ($Action) {
        "ssh" {
            Open-SshShell
        }
        "status" {
            Upload-ScriptOnly
            Show-Status
        }
        "logs" {
            Upload-ScriptOnly
            Show-Logs
        }
        "bootstrap" {
            New-DeployArchive
            Upload-Assets
            Invoke-RemoteSetup -RemoteAction "bootstrap"
        }
        "deploy" {
            New-DeployArchive
            Upload-Assets
            Invoke-RemoteSetup -RemoteAction "deploy"
        }
        "full" {
            New-DeployArchive
            Upload-Assets
            Invoke-RemoteSetup -RemoteAction "full"
        }
    }
}
finally {
    if (Test-Path $TempArchive) {
        Remove-Item $TempArchive -Force -ErrorAction SilentlyContinue
    }
}
