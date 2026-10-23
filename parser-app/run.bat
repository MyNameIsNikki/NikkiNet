@echo off
chcp 65001 >nul
title NikkiNet server parser
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ERROR] Python 3.8+ not found in PATH.
  echo Install Python from https://www.python.org/downloads/
  echo and enable "Add python.exe to PATH" during setup.
  echo.
  pause
  exit /b 1
)

python parser.py %*
echo.
pause
