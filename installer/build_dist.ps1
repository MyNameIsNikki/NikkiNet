# Builds the distributable tree and (optionally) the NikkiNet setup .exe.
#
# Usage:
#   pwsh -File installer/build_dist.ps1 -Version 1.1.0 -Compile
#
# The result is installer/.build/dist (app + bundled Python 3.12 + tools).
# With -Compile it also produces installer/Output/NikkiNet-Setup-<Version>.exe
# (requires Inno Setup 6).
param(
    [string]$Version = "1.1.0",
    [switch]$Compile
)

$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

$here  = $PSScriptRoot
$root  = Split-Path -Parent $here
$build = Join-Path $here ".build"
$dist  = Join-Path $build "dist"
$dl    = Join-Path $build "dl"
$tools = Join-Path $dist "tools"

Write-Host "== NikkiNet build $Version =="

if (Test-Path $build) { Remove-Item $build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $dist, $tools, $dl | Out-Null

function Get-Download([string]$Url, [string]$Dest) {
    if (-not (Test-Path $Dest)) {
        Write-Host "downloading $Url"
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    }
}

# --- app files ---------------------------------------------------------
Get-ChildItem $root -Filter "*.py" -File | Copy-Item -Destination $dist -Force
Copy-Item (Join-Path $root "start.bat")     (Join-Path $dist "start.bat")     -Force
Copy-Item (Join-Path $root "install.bat")   (Join-Path $dist "install.bat")   -Force
Copy-Item (Join-Path $root "uninstall.bat") (Join-Path $dist "uninstall.bat") -Force
Copy-Item (Join-Path $root "README.txt")    (Join-Path $dist "README.txt")    -Force
Copy-Item (Join-Path $here "nikkinet.ico")  (Join-Path $dist "nikkinet.ico")  -Force

# --- tools (sing-box + wintun) ----------------------------------------
$repoTools = Join-Path $root "tools"
New-Item -ItemType Directory -Force -Path $repoTools | Out-Null

$singbox = Join-Path $repoTools "sing-box.exe"
if (-not (Test-Path $singbox)) {
    $zip = Join-Path $dl "singbox.zip"
    Get-Download "https://github.com/SagerNet/sing-box/releases/download/v1.14.3/sing-box-1.14.3-windows-amd64.zip" $zip
    $tmp = Join-Path $dl "singbox"
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $found = Get-ChildItem $tmp -Recurse -Filter "sing-box.exe" | Select-Object -First 1
    if (-not $found) { throw "sing-box.exe not found in archive" }
    Copy-Item $found.FullName $singbox -Force
}

$wintun = Join-Path $repoTools "wintun.dll"
if (-not (Test-Path $wintun)) {
    $zip = Join-Path $dl "wintun.zip"
    Get-Download "https://www.wintun.net/builds/wintun-0.14.1.zip" $zip
    $tmp = Join-Path $dl "wintun"
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $found = Get-ChildItem $tmp -Recurse -Filter "wintun.dll" |
             Where-Object { $_.FullName -match "amd64|x64" } | Select-Object -First 1
    if (-not $found) { throw "wintun.dll not found in archive" }
    Copy-Item $found.FullName $wintun -Force
}

Copy-Item $singbox (Join-Path $tools "sing-box.exe") -Force
Copy-Item $wintun  (Join-Path $tools "wintun.dll")   -Force

# --- bundled Python runtime (so recipients need no Python) ------------
$pyZip = Join-Path $dl "python-embed.zip"
Get-Download "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip" $pyZip
Expand-Archive -Path $pyZip -DestinationPath $dist -Force

$py = Join-Path $dist "python.exe"
if (-not (Test-Path $py)) { throw "python.exe was not extracted" }

# --- self-test of the assembled tree ----------------------------------
Push-Location $dist
try {
    & $py -B -c "import ssl, ctypes, winreg, json, urllib.request, http.server, zipfile, shutil, subprocess; print('runtime imports ok')"
    if ($LASTEXITCODE -ne 0) { throw "bundled Python failed the stdlib import test" }

    & $py -B -c "import ui, singbox, subs, warp, appupdate, version; print('app modules ok', version.APP_VERSION)"
    if ($LASTEXITCODE -ne 0) { throw "app modules failed to import under the bundled runtime" }
} finally {
    Pop-Location
}

$sizeMb = [math]::Round(((Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
Write-Host "dist ready: $dist ($sizeMb MB)"

# --- compile the setup exe --------------------------------------------
if ($Compile) {
    $iscc = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) { throw "ISCC.exe not found - install Inno Setup 6 first" }

    Write-Host "compiling setup with $iscc"
    & $iscc "/DAppVer=$Version" (Join-Path $here "nikkinet.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed (exit $LASTEXITCODE)" }

    $setup = Join-Path $here ("Output\NikkiNet-Setup-$Version.exe")
    if (-not (Test-Path $setup)) { throw "setup exe was not produced: $setup" }
    $setupMb = [math]::Round((Get-Item $setup).Length / 1MB, 1)
    Write-Host "SETUP: $setup ($setupMb MB)"
}
