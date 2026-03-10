# ============================================================
#  DivineMesh Node — Windows One-Line Installer
#  Run in PowerShell as Administrator:
#  irm https://divinemesh.com/install.ps1 | iex
# ============================================================

$ErrorActionPreference = "Stop"
$REPO = "https://github.com/divinemesh/divinemesh"
$COORDINATOR = "https://coordinator.divinemesh.com"
$INSTALL_DIR = "$env:USERPROFILE\.divinemesh"

function Write-Banner {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║          ✝  DivineMesh Node Installer  ✝             ║" -ForegroundColor Yellow
    Write-Host "║   'For where two or three gather in my name...'      ║" -ForegroundColor Yellow
    Write-Host "║                    — Matthew 18:20                   ║" -ForegroundColor Yellow
    Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
}

function Write-Step   { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-OK     { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Info   { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Blue }
function Write-Warn   { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Fail   { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

Write-Banner

# ── Check Admin ──────────────────────────────────────────────
Write-Step "Checking permissions..."
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warn "Not running as Administrator. Some features may not install correctly."
    Write-Warn "For best results, right-click PowerShell and choose 'Run as Administrator'"
}

# ── Check Python ─────────────────────────────────────────────
Write-Step "Checking Python..."
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split(".")
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 10) {
                $python = $cmd
                Write-OK "Found Python $ver ($cmd)"
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Warn "Python 3.10+ not found. Opening download page..."
    Write-Info "Please install Python from: https://www.python.org/downloads/"
    Write-Info "Make sure to check 'Add Python to PATH' during installation!"
    Start-Process "https://www.python.org/downloads/"
    Read-Host "Press Enter after Python is installed, then re-run this script"
    exit 1
}

# ── Check Git ────────────────────────────────────────────────
Write-Step "Checking Git..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "Git not found. Opening download page..."
    Write-Info "Please install Git from: https://git-scm.com/download/win"
    Start-Process "https://git-scm.com/download/win"
    Read-Host "Press Enter after Git is installed, then re-run this script"
    exit 1
}
Write-OK "Git found: $(git --version)"

# ── Download DivineMesh ──────────────────────────────────────
Write-Step "Downloading DivineMesh..."
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null

if (Test-Path "$INSTALL_DIR\repo") {
    Write-Info "Existing install found. Updating..."
    Set-Location "$INSTALL_DIR\repo"
    git pull origin main
} else {
    Write-Info "Cloning from GitHub..."
    git clone $REPO "$INSTALL_DIR\repo"
}
Write-OK "DivineMesh downloaded to $INSTALL_DIR\repo"

# ── Create Virtual Environment ───────────────────────────────
Write-Step "Setting up Python environment..."
Set-Location "$INSTALL_DIR\repo"
& $python -m venv "$INSTALL_DIR\venv"
& "$INSTALL_DIR\venv\Scripts\pip" install --upgrade pip -q
& "$INSTALL_DIR\venv\Scripts\pip" install -r requirements.txt -q
Write-OK "Python environment ready"

# ── Create Launcher Batch File ───────────────────────────────
Write-Step "Creating launcher..."
$launcherDir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null

$launcherContent = @"
@echo off
call "$INSTALL_DIR\venv\Scripts\activate.bat"
cd /d "$INSTALL_DIR\repo"
python -m client.daemon %*
"@
$launcherContent | Out-File -FilePath "$launcherDir\divinemesh.bat" -Encoding ASCII

# Add to PATH
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*$launcherDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$launcherDir", "User")
    Write-OK "Added to PATH"
}

# ── Create Windows Service (Task Scheduler) ─────────────────
Write-Step "Creating auto-start task..."
$taskName = "DivineMeshNode"
$action = New-ScheduledTaskAction -Execute "$launcherDir\divinemesh.bat" -Argument "start"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-OK "Auto-start task created (will start when you log in)"
} catch {
    Write-Warn "Could not create auto-start task (requires Admin). You can start manually."
}

# ── First Run ────────────────────────────────────────────────
Write-Step "Setting up your node identity..."
Set-Location "$INSTALL_DIR\repo"
& "$INSTALL_DIR\venv\Scripts\python" -m client.daemon register

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║          ✝  Installation Complete!  ✝                ║" -ForegroundColor Yellow
Write-Host "╠══════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "║                                                      ║" -ForegroundColor Yellow
Write-Host "║  Start your node:   divinemesh start                 ║" -ForegroundColor Green
Write-Host "║  Check status:      divinemesh status                ║" -ForegroundColor Green
Write-Host "║  View earnings:     divinemesh earnings              ║" -ForegroundColor Green
Write-Host "║  Stop node:         divinemesh stop                  ║" -ForegroundColor Green
Write-Host "║                                                      ║" -ForegroundColor Yellow
Write-Host "║  Dashboard:  https://divinemesh.com                  ║" -ForegroundColor Cyan
Write-Host "║  Network:    https://coordinator.divinemesh.com      ║" -ForegroundColor Cyan
Write-Host "║                                                      ║" -ForegroundColor Yellow
Write-Host "║  'Give, and it will be given to you.' Luke 6:38      ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "NOTE: Open a new PowerShell window to use 'divinemesh' command." -ForegroundColor Yellow
Write-Host ""
