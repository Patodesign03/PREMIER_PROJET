# ============================================
#  Solitaire Klondike Solver - Setup and Run
#  PowerShell Launcher Script
# ============================================

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Solitaire Klondike - Assistant de Resolution" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check Python availability
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python detecte : $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERREUR] Python n'est pas installe ou n'est pas dans le PATH." -ForegroundColor Red
    Write-Host "Veuillez installer Python 3.10+ depuis https://www.python.org/"
    Exit 1
}

# Check or create virtual environment
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$VenvPip = Join-Path $ScriptDir ".venv\Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[INFO] Creation de l'environnement virtuel .venv..." -ForegroundColor Yellow
    python -m venv .venv
    if (-not (Test-Path $VenvPython)) {
        Write-Host "[ERREUR] Impossible de creer l'environnement virtuel." -ForegroundColor Red
        Exit 1
    }
    Write-Host "[OK] Environnement virtuel cree." -ForegroundColor Green
} else {
    Write-Host "[OK] Environnement virtuel existant detecte." -ForegroundColor Green
}

# Install dependencies
Write-Host "[INFO] Installation / verification des dependances..." -ForegroundColor Yellow
& $VenvPip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Echec de l'installation des dependances." -ForegroundColor Red
    Exit 1
}
Write-Host "[OK] Dependances pretes." -ForegroundColor Green

# Quick tests
Write-Host ""
Write-Host "[INFO] Execution des tests..." -ForegroundColor Yellow
& $VenvPython -m pytest tests/ -q --tb=short
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ATTENTION] Certains tests ont echoue, mais le serveur demarre quand meme." -ForegroundColor DarkYellow
} else {
    Write-Host "[OK] Tous les tests sont valides." -ForegroundColor Green
}

# Launch the server
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Demarrage du serveur web..." -ForegroundColor Green
Write-Host "  Ouvrez votre navigateur a l'adresse :" -ForegroundColor White
Write-Host "  http://localhost:5055" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Appuyez sur Ctrl+C pour arreter le serveur" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# Open default browser automatically
Start-Process "http://localhost:5055"

# Run Flask app with the venv python
& $VenvPython app.py
