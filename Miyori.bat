@echo off
setlocal EnableExtensions
title Miyori Kitsune AI
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%~dp0"

set "CHECK_MODE=0"
if /I "%~1"=="--check" set "CHECK_MODE=1"

echo.
echo ============================================
echo          MIYORI KITSUNE AI
echo ============================================
echo Location: %CD%
echo.

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found.
    goto :fail
)
if not exist "setup-portable.ps1" (
    echo [ERROR] setup-portable.ps1 not found.
    goto :fail
)
if not exist "miyori\launcher.py" (
    echo [ERROR] miyori\launcher.py not found.
    goto :fail
)

set "RUN_PYTHON="
set "SYSTEM_PYTHON="

rem 1) Prefer Miyori's own portable runtime when it is compatible.
if exist "runtime\python.exe" (
    "runtime\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        echo [1/4] Portable Python runtime found.
        set "RUN_PYTHON=%CD%\runtime\python.exe"
        goto :python_ready
    )
    echo [1/4] Portable runtime is too old or damaged. Rebuilding it...
    rmdir /S /Q "runtime" >nul 2>nul
)

rem 2) Reuse a local virtual environment only when its Python is supported.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        echo [1/4] Local virtual environment found.
        set "RUN_PYTHON=%CD%\.venv\Scripts\python.exe"
        goto :python_ready
    )
    echo [1/4] Local virtual environment is incompatible. Recreating it...
    rmdir /S /Q ".venv" >nul 2>nul
)

rem 3) Find a supported system Python (3.10+).
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 set "SYSTEM_PYTHON=py -3"
)

if not defined SYSTEM_PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
        if not errorlevel 1 set "SYSTEM_PYTHON=python"
    )
)

if defined SYSTEM_PYTHON (
    echo [1/4] Creating local virtual environment with supported Python...
    %SYSTEM_PYTHON% -m venv ".venv"
    if errorlevel 1 goto :fail
    set "RUN_PYTHON=%CD%\.venv\Scripts\python.exe"
    goto :python_ready
)

rem 4) No supported Python: bootstrap a self-contained runtime next to Miyori.
echo [1/4] Supported Python was not found. Creating Miyori portable runtime...
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\setup-portable.ps1"
if errorlevel 1 goto :fail

if not exist "runtime\python.exe" goto :fail
set "RUN_PYTHON=%CD%\runtime\python.exe"

:python_ready
"%RUN_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Miyori requires Python 3.10 or newer.
    goto :fail
)

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo [setup] Created .env from .env.example.
)

if "%CHECK_MODE%"=="0" (
    echo [2/4] Checking trusted GitHub updates...
    "%RUN_PYTHON%" -m miyori.updater --auto
    echo.
) else (
    echo [2/4] Update check skipped in --check mode.
)

echo [3/4] Installing/checking Python dependencies...
"%RUN_PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

if "%CHECK_MODE%"=="1" (
    echo [4/4] Running startup preflight...
    "%RUN_PYTHON%" -m miyori.launcher --check --no-browser
    if errorlevel 1 goto :fail
    echo.
    echo [OK] Portable ZIP startup check passed.
    exit /b 0
)

echo [4/4] Starting Miyori...
echo Web: http://127.0.0.1:8765
echo Startup log: %CD%\logs\last-startup.log
echo Close this window or press Ctrl+C to stop the server.
echo.
"%RUN_PYTHON%" -m miyori.launcher
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo [ERROR] Miyori could not start.
echo Startup log: %CD%\logs\last-startup.log
echo.
echo Check the messages above. On first setup an internet connection
echo may be required to download Python and install dependencies.
if defined CI exit /b 1
pause
exit /b 1
