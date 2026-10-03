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

set "PYTHON_EXE="

where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_EXE=py -3"

if not defined PYTHON_EXE (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python 3 was not found.
    echo Install Python 3.11 or newer and enable "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating portable virtual environment...
    %PYTHON_EXE% -m venv ".venv"
    if errorlevel 1 goto :fail
) else (
    echo [1/3] Virtual environment found.
)

echo [2/3] Checking dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
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
".venv\Scripts\python.exe" app.py
goto :eof

:fail
echo.
echo [ERROR] Miyori could not start.
pause
exit /b 1
