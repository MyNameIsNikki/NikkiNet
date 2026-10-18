@echo off
setlocal
title Proxy App - Installer
cd /d "%~dp0"

rem ===== 0. Must be extracted from the zip first =====
if not exist "proxy_app.py" (
  echo [ERROR] proxy_app.py not found next to install.bat.
  echo Extract the WHOLE zip archive to a folder first,
  echo then run install.bat from that folder.
  pause
  exit /b 1
)

rem ===== 1. Elevate to administrator =====
net session >nul 2>&1
if %errorlevel% equ 0 goto elevated

echo Requesting administrator privileges...
powershell -NoProfile -Command "try { Start-Process -Verb RunAs -FilePath '%~f0' } catch { exit 1 }"
if %errorlevel% equ 0 exit /b

echo.
echo [ERROR] UAC was declined or blocked by SmartScreen/antivirus.
echo Right-click install.bat and choose "Run as administrator".
echo.
pause
exit /b 1

:elevated
echo =====================================================
echo   Proxy App installer
echo   Install folder: %LOCALAPPDATA%\ProxyApp
echo =====================================================
echo.

rem ===== 2. Check for a working Python 3.8+ =====
set "PYGATE=import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
python -c "%PYGATE%" >nul 2>&1
if %errorlevel% equ 0 goto pyok
py -3 -c "%PYGATE%" >nul 2>&1
if %errorlevel% equ 0 goto pyok

echo Python not found or too old - installing Python 3.12.
echo Internet connection required (about 30 MB, 1-3 minutes).
echo.

rem -- use a bundled installer if present, otherwise download --
set "PYSETUP="
if exist "%~dp0python-3.12.10-amd64.exe" set "PYSETUP=%~dp0python-3.12.10-amd64.exe"
if not defined PYSETUP if exist "%~dp0python-3.12.10.exe" set "PYSETUP=%~dp0python-3.12.10.exe"
if defined PYSETUP goto installpython

set "PYSETUP=%TEMP%\python-3.12.10-setup.exe"
set "PYURL=https://www.python.org/ftp/python/3.12.10/python-3.12.10.exe"
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" set "PYURL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"

echo Downloading Python installer...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%PYURL%' -OutFile '%PYSETUP%' } catch { exit 1 }"
if %errorlevel% neq 0 (
  echo.
  echo [ERROR] Could not download Python.
  echo Check the internet connection and run install.bat again,
  echo or install Python manually from https://www.python.org/downloads/
  echo ^(enable "Add python.exe to PATH"^) and rerun install.bat.
  pause
  exit /b 1
)
set "PYDOWNLOADED=1"

:installpython
echo Installing Python silently, please wait...
"%PYSETUP%" /passive InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_test=0
if defined PYDOWNLOADED del /q "%PYSETUP%" >nul 2>&1

rem -- re-check: the py launcher is usable right away --
py -3 -c "%PYGATE%" >nul 2>&1
if %errorlevel% equ 0 goto pyok
python -c "%PYGATE%" >nul 2>&1
if %errorlevel% equ 0 goto pyok
for %%D in ("%ProgramFiles%\Python312" "%ProgramFiles(x86)%\Python312-32" "%LOCALAPPDATA%\Programs\Python\Python312") do (
  if exist "%%~D\python.exe" set "PYFULL=%%~D\python.exe" & goto pyfull
)
echo.
echo [ERROR] Python installation did not complete.
echo Install Python manually from https://www.python.org/downloads/
echo ^(enable "Add python.exe to PATH"^) and run install.bat again.
pause
exit /b 1

:pyfull
echo Found Python at %PYFULL%
set "PATH=%PYFULL:~0,-11%;%PATH%"

:pyok
echo Python is ready.
echo.

rem ===== 3. Stop a running copy of the app =====
set "DEST=%LOCALAPPDATA%\ProxyApp"
if not exist "%DEST%\.lock" goto nolock
set /p OLDPID=<"%DEST%\.lock"
taskkill /PID %OLDPID% /F >nul 2>&1
:nolock
taskkill /IM sing-box.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

rem ===== 4. Copy app files =====
echo Installing app files to %DEST% ...
robocopy "%~dp0." "%DEST%" /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /NP /XD __pycache__ .git .github /XF install.bat config.json .lock *.log sing-box-config.json test-*.json .gitignore README.md
if %errorlevel% geq 8 (
  echo.
  echo [ERROR] Could not copy files to %DEST%.
  echo Close the app if it is running and run install.bat again.
  pause
  exit /b 1
)

rem first install: copy config.json with the shared servers; upgrades keep the existing one
if not exist "%DEST%\config.json" copy /y "%~dp0config.json" "%DEST%\config.json" >nul

if not exist "%DEST%\tools\sing-box.exe" (
  echo.
  echo [WARNING] tools\sing-box.exe is missing - probably removed by antivirus.
  echo The app will try to download it at first start,
  echo or add an antivirus exclusion ^(see below^).
)

rem ===== 5. Shortcuts (Desktop + Start menu) =====
echo Creating shortcuts...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; foreach($base in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { try { $s = $ws.CreateShortcut((Join-Path $base 'Proxy App.lnk')); $s.TargetPath = '%DEST%\start.bat'; $s.WorkingDirectory = '%DEST%'; $s.IconLocation = '%SystemRoot%\System32\shell32.dll,13'; $s.Description = 'Proxy App'; $s.Save() } catch {} }"

rem ===== 6. Optional Windows Defender exclusion =====
echo.
powershell -NoProfile -Command "exit [int]((Get-Service WinDefend -ErrorAction SilentlyContinue).Status -ne 'Running')"
if %errorlevel% neq 0 (
  echo Windows Defender is not active on this PC - most likely another
  echo antivirus is installed and has disabled it. If that antivirus
  echo removes sing-box.exe, add this folder to ITS exclusions manually:
  echo     %DEST%
  goto afterdefender
)
choice /C YN /N /M "Add Windows Defender exclusion for the app folder (recommended, antivirus often removes sing-box.exe)? [Y/N]: "
if %errorlevel% equ 1 powershell -NoProfile -Command "try { Add-MpPreference -ExclusionPath '%DEST%' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess '%DEST%\tools\sing-box.exe' -ErrorAction SilentlyContinue } catch {}"
:afterdefender
echo.

rem ===== 7. Finish =====
echo =====================================================
echo   Installation complete!
echo.
echo   App folder:  %DEST%
echo   Shortcuts:   "Proxy App" on the Desktop and in Start menu
echo   Admin panel: http://127.0.0.1:8000
echo   Local proxy: 127.0.0.1:8888
echo =====================================================
echo.
choice /C YN /N /M "Start Proxy App now? [Y/N]: "
if %errorlevel% equ 1 start "" "%DEST%\start.bat"
echo.
pause
exit /b 0
