@echo off
title Proxy App
cd /d "%~dp0"

rem ===== 0. Make sure the app was extracted from the archive =====
if not exist "proxy_app.py" (
  echo [ERROR] proxy_app.py not found next to start.bat.
  echo Extract the whole archive to a folder first -
  echo do not run the file from inside the zip.
  pause
  exit /b 1
)

rem ===== 1. Elevate to administrator =====
net session >nul 2>&1
if %errorlevel% equ 0 goto run

echo Requesting administrator privileges (needed for full VPN)...
powershell -NoProfile -Command "try { Start-Process -Verb RunAs -FilePath '%~f0' } catch { exit 1 }"
if %errorlevel% equ 0 exit /b

echo.
echo [ERROR] UAC was declined or the file was blocked by SmartScreen/antivirus.
echo Right-click start.bat and choose "Run as administrator".
echo.
pause
exit /b 1

:run
rem ===== 2. Find a working Python 3.8+ =====
set "PYCMD="
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if %errorlevel% equ 0 set "PYCMD=python" & goto runapp
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if %errorlevel% equ 0 set "PYCMD=py -3" & goto runapp
python --version >nul 2>&1
if %errorlevel% equ 0 goto pyold
py -3 --version >nul 2>&1
if %errorlevel% equ 0 goto pyold

echo.
echo =============================================================
echo  [ERROR] Python is not installed on this computer.
echo  Run install.bat once - it installs everything automatically.
echo  Or get Python from https://www.python.org/downloads/
echo  and enable "Add python.exe to PATH" during setup.
echo =============================================================
echo.
pause
exit /b 1

:pyold
echo.
echo [ERROR] The installed Python is older than 3.8.
echo Run install.bat to install a current Python automatically.
echo.
pause
exit /b 1

:runapp
rem ===== 3. Start the app =====
echo Starting Proxy App...
echo.
%PYCMD% proxy_app.py
set "EC=%errorlevel%"
echo.
if %EC% neq 0 echo [ERROR] App exited with code %EC%. See messages above and crash.log
pause
