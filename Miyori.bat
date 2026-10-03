@echo off
setlocal EnableExtensions
title Miyori Kitsune AI

cd /d "%~dp0"

echo.
echo ============================================
echo          MIYORI KITSUNE AI
echo ============================================
echo Location: %CD%
echo.

set "RUN_PYTHON="

rem 1) Prefer Miyori's own runtime. This makes the folder movable between drives.
if exist "runtime\python.exe" (
    echo [1/3] Portable Python runtime found.
    set "RUN_PYTHON=%CD%\runtime\python.exe"
    goto :python_ready
)

rem 2) If no bundled runtime exists, use system Python to create a local venv.
set "SYSTEM_PYTHON="
where py >nul 2>nul
if %errorlevel%==0 set "SYSTEM_PYTHON=py -3"

if not defined SYSTEM_PYTHON (
    where python >nul 2>nul
    if %errorlevel%==0 set "SYSTEM_PYTHON=python"
)

if defined SYSTEM_PYTHON (
    if not exist ".venv\Scripts\python.exe" (
        echo [1/3] Creating local virtual environment...
        %SYSTEM_PYTHON% -m venv ".venv"
        if errorlevel 1 goto :fail
    ) else (
        echo [1/3] Local virtual environment found.
    )
    set "RUN_PYTHON=%CD%\.venv\Scripts\python.exe"
    goto :python_ready
)

rem 3) No Python at all: bootstrap a self-contained runtime next to Miyori.
echo [1/3] Python was not found. Creating Miyori portable runtime...
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\setup-portable.ps1"
if errorlevel 1 goto :fail

if not exist "runtime\python.exe" goto :fail
set "RUN_PYTHON=%CD%\runtime\python.exe"

:python_ready
echo [update] Checking trusted GitHub updates...
"%RUN_PYTHON%" -m miyori.updater --auto
echo.
echo [2/3] Checking dependencies...
"%RUN_PYTHON%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo.
    echo [SETUP] Created .env from .env.example.
    echo Open .env and set CLOUDRU_API_KEY and CLOUDRU_MODEL_ID.
    echo You can still open the website now to verify the local interface.
    echo.
)

echo [3/3] Starting Miyori...
echo Web: http://127.0.0.1:8765
echo Close this window or press Ctrl+C to stop the server.
echo.
"%RUN_PYTHON%" app.py
goto :eof

:fail
echo.
echo [ERROR] Miyori could not start.
echo Check your internet connection during the first portable setup,
echo or inspect the messages above.
pause
exit /b 1
