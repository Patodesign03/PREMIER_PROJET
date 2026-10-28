@echo off
REM ============================================
REM  Solitaire Klondike Solver - Setup and Run
REM  Windows Launcher Script
REM ============================================

echo ============================================
echo  Solitaire Klondike - Assistant de Resolution
echo ============================================
echo.

REM Check Python availability
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou n'est pas dans le PATH.
    echo Veuillez installer Python 3.10+ depuis https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python detecte.

REM Navigate to project directory (same as this script)
cd /d "%~dp0"

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo [INFO] Creation de l'environnement virtuel...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
    echo [OK] Environnement virtuel cree.
) else (
    echo [OK] Environnement virtuel existant detecte.
)

REM Activate virtual environment and install dependencies
echo [INFO] Installation des dependances...
call .venv\Scripts\activate.bat

.venv\Scripts\pip.exe install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERREUR] Impossible d'installer les dependances.
    pause
    exit /b 1
)
echo [OK] Dependances installees.

REM Run tests (optional, quick check)
echo.
echo [INFO] Execution des tests rapides...
.venv\Scripts\python.exe -m pytest tests/ -x -q --tb=short 2>nul
if errorlevel 1 (
    echo [ATTENTION] Certains tests ont echoue. L'application va quand meme demarrer.
) else (
    echo [OK] Tests reussis.
)

REM Launch the application
echo.
echo ============================================
echo  Demarrage du serveur web...
echo  Ouvrez votre navigateur a l'adresse :
echo  http://localhost:5055
echo ============================================
echo  Appuyez sur Ctrl+C pour arreter le serveur
echo ============================================
echo.

.venv\Scripts\python.exe app.py

pause
