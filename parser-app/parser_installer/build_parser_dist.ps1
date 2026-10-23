param(
    [string]$Version = "1.0.0",
    [switch]$Compile
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $PSScriptRoot ".build"
$dist = Join-Path $build "dist"
$dl = Join-Path $build "dl"

if (Test-Path $build) { Remove-Item $build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $dist, $dl | Out-Null

$files = @(
    "parser_ui.py", "netparse.py", "singbox.py", "subs.py", "webscan.py",
    "start_parser.bat", "README_PARSER.txt"
)
foreach ($f in $files) {
    Copy-Item (Join-Path $root $f) (Join-Path $dist $f)
}

$icon = Join-Path $PSScriptRoot "parser.ico"
if (-not (Test-Path $icon)) {
    $repo = Split-Path -Parent $root
    $icon = Join-Path $repo "installer\nikkinet.ico"
}
Copy-Item $icon (Join-Path $dist "parser.ico")

$pyZip = Join-Path $dl "python-embed.zip"
$repo = Split-Path -Parent $root
$caches = @(
    (Join-Path $repo "installer\.build\dl\python-embed.zip"),
    (Join-Path (Split-Path -Parent $repo) "prox\installer\.build\dl\python-embed.zip"),
    (Join-Path $repo ".build\dl\python-embed.zip")
)
$proxCache = $caches | Where-Object { Test-Path $_ } | Select-Object -First 1
if (Test-Path $proxCache) {
    Copy-Item $proxCache $pyZip
    Write-Host "python embeddable: from prox cache"
} else {
    $url = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
    Write-Host "downloading $url"
    Invoke-WebRequest $url -OutFile $pyZip -UseBasicParsing
}
Expand-Archive $pyZip $dist -Force
New-Item -ItemType Directory -Force -Path (Join-Path $dist "tools") | Out-Null

& (Join-Path $dist "python.exe") -B -c "import netparse, singbox, subs, webscan; print('runtime OK')"
if ($LASTEXITCODE -ne 0) { throw "runtime self-test failed" }

$size = [math]::Round((Get-ChildItem $dist -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "dist: $dist ($size MB)"

if (-not $Compile) { return }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "ISCC.exe not found. Install Inno Setup 6." }

& $iscc "/DAppVer=$Version" (Join-Path $PSScriptRoot "parser.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with code $LASTEXITCODE" }

$out = Join-Path $PSScriptRoot "Output\NikkiNet-Parser-Setup-$Version.exe"
if (-not (Test-Path $out)) { throw "output not found: $out" }
$mb = [math]::Round((Get-Item $out).Length / 1MB, 1)
Write-Host "SETUP: $out ($mb MB)"
