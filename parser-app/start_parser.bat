@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title NikkiNet Parser

if exist "%~dp0python.exe" goto bundled

where python >nul 2>&1
if errorlevel 1 goto nopython
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if errorlevel 1 goto nopython

python parser_ui.py
if errorlevel 1 pause
exit /b 0

:bundled
"%~dp0python.exe" parser_ui.py
if errorlevel 1 pause
exit /b 0

:nopython
echo.
echo Python 3.8+ not found.
echo Install Python from https://www.python.org/downloads/
echo or use the NikkiNet Parser installer.
echo.
pause
exit /b 1
