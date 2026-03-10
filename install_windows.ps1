# DivineMesh Windows Installer
# "The Lord is my strength and my shield; my heart trusts in him." - Psalm 28:7
#
# One-line install (Run as Administrator in PowerShell):
#   irm https://divinemesh.com/install.sh/windows | iex

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$REPO         = "https://github.com/divinemesh/divinemesh"
$INSTALL_DIR  = "$env:USERPROFILE\.divinemesh"
$VERSION      = "1.0.0"
$DOCKER_URL   = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"

function Write-Banner {
    Write-Host @"

  ██████╗ ██╗██╗   ██╗██╗███╗   ██╗███████╗    ███╗   ███╗███████╗███████╗██╗  ██╗
  ██╔══██╗██║██║   ██║██║████╗  ██║██╔════╝    ████╗ ████║██╔════╝██╔════╝██║  ██║
  ██║  ██║██║██║   ██║██║██╔██╗ ██║█████╗      ██╔████╔██║█████╗  ███████╗███████║
  ██║  ██║██║╚██╗ ██╔╝██║██║╚██╗██║██╔══╝      ██║╚██╔╝██║██╔══╝  ╚════██║██╔══██║
  ██████╔╝██║ ╚████╔╝ ██║██║ ╚████║███████╗    ██║ ╚═╝ ██║███████╗███████║██║  ██║
  ╚═════╝ ╚═╝  ╚═══╝  ╚═╝╚═╝  ╚═══╝╚══════╝    ╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝

  "For God so loved the world that he gave his one and only Son" - John 3:16
  DivineMesh v$VERSION — Windows Installer
"@ -ForegroundColor Cyan
}

function Test-Admin {
    $currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-Chocolatey {
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "[✓] Chocolatey already installed" -ForegroundColor Green
        return
    }
    Write-Host "[→] Installing Chocolatey package manager..." -ForegroundColor Cyan
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "[✓] Chocolatey installed" -ForegroundColor Green
}

function Install-Dependencies {
    Write-Host "[→] Installing dependencies (Python, Git, Docker)..." -ForegroundColor Cyan
    $deps = @()
    if (-not (Get-Command python3 -ErrorAction SilentlyContinue) -and
        -not (Get-Command python -ErrorAction SilentlyContinue)) {
        $deps += "python"
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { $deps += "git" }
    if ($deps.Count -gt 0) {
        choco install $deps -y --no-progress
    }
    # Docker Desktop
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "[→] Downloading Docker Desktop..." -ForegroundColor Cyan
        $dockerInstaller = "$env:TEMP\DockerInstaller.exe"
        Invoke-WebRequest -Uri $DOCKER_URL -OutFile $dockerInstaller -UseBasicParsing
        Start-Process -Wait -FilePath $dockerInstaller -ArgumentList "install --quiet"
        Write-Host "[✓] Docker Desktop installed — please restart and re-run installer" -ForegroundColor Yellow
    }
    Write-Host "[✓] Dependencies ready" -ForegroundColor Green
}

function Install-DivineMesh {
    Write-Host "[→] Installing DivineMesh..." -ForegroundColor Cyan

    New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
    New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\data" | Out-Null

    # Clone repository
    if (Test-Path "$INSTALL_DIR\repo") {
        Write-Host "[→] Updating existing installation..."
        git -C "$INSTALL_DIR\repo" pull --quiet
    } else {
        git clone --depth 1 $REPO "$INSTALL_DIR\repo" --quiet
    }

    # Create Python venv
    $pythonCmd = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
    & $pythonCmd -m venv "$INSTALL_DIR\venv"
    & "$INSTALL_DIR\venv\Scripts\pip.exe" install --quiet --upgrade pip
    & "$INSTALL_DIR\venv\Scripts\pip.exe" install --quiet -r "$INSTALL_DIR\repo\requirements.txt"

    # Create launcher batch file
    $launcherContent = @"
@echo off
REM DivineMesh Node Launcher
REM "I can do all things through Christ who strengthens me." - Phil 4:13
set DIVINEMESH_HOME=$INSTALL_DIR
"$INSTALL_DIR\venv\Scripts\python.exe" -m client.daemon %*
"@
    Set-Content -Path "$INSTALL_DIR\divinemesh.bat" -Value $launcherContent

    # Add to PATH
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$INSTALL_DIR*") {
        [System.Environment]::SetEnvironmentVariable(
            "Path",
            "$userPath;$INSTALL_DIR",
            "User"
        )
        Write-Host "[✓] Added $INSTALL_DIR to user PATH" -ForegroundColor Green
    }

    # Create Windows Task for auto-start (optional)
    $taskAction = New-ScheduledTaskAction -Execute "$INSTALL_DIR\divinemesh.bat" -Argument "start"
    $taskTrigger = New-ScheduledTaskTrigger -AtLogOn
    $taskSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3
    Register-ScheduledTask -TaskName "DivineMesh Node" `
        -Action $taskAction -Trigger $taskTrigger `
        -Settings $taskSettings -RunLevel Limited `
        -Force | Out-Null
    Write-Host "[✓] Auto-start task registered" -ForegroundColor Green
    Write-Host "[✓] DivineMesh installed to $INSTALL_DIR" -ForegroundColor Green
}

function Show-NextSteps {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║   DivineMesh Installation Complete!                  ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next steps:"
    Write-Host "  1. Register your node:"
    Write-Host "     divinemesh register" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  2. Start the daemon:"
    Write-Host "     divinemesh start" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  3. Open Dashboard: http://127.0.0.1:8080" -ForegroundColor Cyan
    Write-Host ""
    Write-Host '  "The Lord is my light and my salvation" - Psalm 27:1' -ForegroundColor Yellow
    Write-Host ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
Write-Banner
if (-not (Test-Admin)) {
    Write-Host "[!] WARNING: Not running as Administrator. Some steps may fail." -ForegroundColor Yellow
    Write-Host "    Restart PowerShell as Administrator for best results." -ForegroundColor Yellow
}
Install-Chocolatey
Install-Dependencies
Install-DivineMesh
Show-NextSteps
