@echo off
setlocal
title Proxy App - Uninstall
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% equ 0 goto un

echo Requesting administrator privileges...
powershell -NoProfile -Command "try { Start-Process -Verb RunAs -FilePath '%~f0' } catch { exit 1 }"
if %errorlevel% equ 0 exit /b
echo [ERROR] UAC declined. Right-click uninstall.bat - Run as administrator.
pause
exit /b 1

:un
set "DEST=%LOCALAPPDATA%\ProxyApp"

echo Stopping the app...
if not exist "%DEST%\.lock" goto nolock
set /p OLDPID=<"%DEST%\.lock"
taskkill /PID %OLDPID% /F >nul 2>&1
:nolock
taskkill /IM sing-box.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

rem remove the LAN proxy firewall rule (if it was enabled)
powershell -NoProfile -Command "Remove-NetFirewallRule -DisplayName 'NikkiNet LAN proxy' -ErrorAction SilentlyContinue" >nul 2>&1

rem make sure the system proxy is not left enabled
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul 2>&1

echo Removing files...
rd /s /q "%DEST%" >nul 2>&1

echo Removing shortcuts...
powershell -NoProfile -Command "foreach($base in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { Remove-Item -LiteralPath (Join-Path $base 'Proxy App.lnk') -ErrorAction SilentlyContinue }"

echo.
echo Done - Proxy App removed.
echo Python was NOT removed (other programs may use it).
echo To remove it too: Settings - Apps - Python 3.12.
pause
exit /b 0
