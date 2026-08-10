@echo off
REM =====================================================================
REM  University Management System - one-click runner for Windows
REM  Just double-click this file (after Python is installed).
REM =====================================================================
title University Management System
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set PY=py
) else (
    set PY=python
)

echo --------------------------------------
echo  Installing Django & libraries (needs internet once)
echo --------------------------------------
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Could not install Django. Is Python installed?
    echo Download it from https://www.python.org/downloads/ and
    echo TICK the box "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

echo.
echo --------------------------------------
echo  Preparing the database
echo --------------------------------------
%PY% manage.py migrate
%PY% manage.py seed_demo

echo.
echo --------------------------------------
echo  Starting the server...
echo  Open this address in your browser:
echo.
echo       http://127.0.0.1:8000
echo.
echo  Press Ctrl+C to stop the server.
echo --------------------------------------
%PY% manage.py runserver
pause
