# Assemble dist\EUVD-mapper from the pinned git tree and vendored wheels.
Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"
$Root = Join-Path $env:TEMP "euvd-mapper-build"
$Repo = "C:\Users\kosin\Documents\EUVD-mapper\tomcat-vulns.html"
$Sha = "dbd9036611e525bcb1abeb8fe8f97ba31dfd487a"
$Python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
Set-Location $Root
. (Join-Path $Root "Invoke-Native.ps1")

function Assert-TextFile {
    param([string]$Path)
    $bytes = [IO.File]::ReadAllBytes($Path)
    foreach ($byte in $bytes) {
        if ($byte -gt 127) { throw "Non-ASCII byte in $Path" }
    }
    if ($Path.EndsWith(".ps1")) {
        $tokens = $null
        $errors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
        if ($errors -and $errors.Count -gt 0) {
            throw "Parse error in ${Path}: $($errors[0].ToString())"
        }
    }
}

if (-not (Test-Path $Python)) { throw "Python 3.12 is missing: $Python" }
$src = Join-Path $Root "src"
$zip = Join-Path $Root "source.zip"
if (Test-Path $src) { Remove-Item $src -Recurse -Force }
New-Item -ItemType Directory -Force -Path $src | Out-Null
if (Test-Path $zip) { Remove-Item $zip -Force }
Invoke-Native -FilePath "git" -ArgumentList @("-C", $Repo, "archive", "--format=zip", "-o", $zip, $Sha)
Expand-Archive -Path $zip -DestinationPath $src -Force
Copy-Item (Join-Path $Root "excel-rid-fix\xlsxinsert.py") (Join-Path $src "euvd_mapper\xlsxinsert.py") -Force

$wheelDir = Join-Path $Root "wheels"
if (Test-Path $wheelDir) { Remove-Item $wheelDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
Invoke-Native -FilePath $Python -ArgumentList @("-m", "pip", "wheel", "--no-deps", "-w", $wheelDir, $src)
Invoke-Native -FilePath $Python -ArgumentList @(
    "-m", "pip", "download", "--only-binary=:all:", "-d", $wheelDir,
    "openpyxl==3.1.5", "tzdata==2026.5", "pip", "setuptools", "wheel"
)
$openpyxl = @(Get-ChildItem $wheelDir -Filter "openpyxl-3.1.5-*.whl")
$et = @(Get-ChildItem $wheelDir -Filter "et_xmlfile-*.whl")
$mapper = @(Get-ChildItem $wheelDir -Filter "euvd_mapper-0.2.0-*.whl")
$tzdata = @(Get-ChildItem $wheelDir -Filter "tzdata-2026.5-*.whl")
$pipWheel = @(Get-ChildItem $wheelDir -Filter "pip-*.whl")
if ($openpyxl.Count -ne 1) { throw "Expected one openpyxl 3.1.5 wheel" }
if ($et.Count -ne 1) { throw "Expected one et_xmlfile wheel" }
if ($mapper.Count -ne 1) { throw "Expected one euvd_mapper wheel" }
if ($tzdata.Count -ne 1) { throw "Expected one tzdata 2026.5 wheel" }
if ($pipWheel.Count -ne 1) { throw "Expected one pip wheel" }

$download = Join-Path $Root "download"
New-Item -ItemType Directory -Force -Path $download | Out-Null
$embedName = "python-3.12.10-embed-amd64.zip"
$embedZip = Join-Path $download $embedName
$embedSpdx = $embedZip + ".spdx.json"
$embedUrl = "https://www.python.org/ftp/python/3.12.10/" + $embedName
if (-not (Test-Path $embedZip)) {
    Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip
}
if (-not (Test-Path $embedSpdx)) {
    Invoke-WebRequest -Uri ($embedUrl + ".spdx.json") -OutFile $embedSpdx
}
Invoke-Native -FilePath $Python -ArgumentList @((Join-Path $Root "verify_embed.py"), $embedZip, $embedSpdx)

$dist = Join-Path $Root "dist\EUVD-mapper"
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $dist "payload\app") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dist "payload\wheels") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dist "payload\bin") | Out-Null
Copy-Item (Join-Path $src "tests") (Join-Path $dist "payload\app\tests") -Recurse
Copy-Item (Join-Path $src "examples") (Join-Path $dist "payload\app\examples") -Recurse
Copy-Item (Join-Path $src "pyproject.toml") (Join-Path $dist "payload\app\pyproject.toml")
Get-ChildItem (Join-Path $dist "payload\app") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem (Join-Path $dist "payload\app") -Recurse -File -Filter "*.pyc" | Remove-Item -Force
Copy-Item (Join-Path $wheelDir "*") (Join-Path $dist "payload\wheels")
Copy-Item $embedZip (Join-Path $dist "payload\$embedName")
Copy-Item (Join-Path $Root "euvd-enrich.cmd") (Join-Path $dist "payload\bin\euvd-enrich.cmd")
Copy-Item (Join-Path $Root "euvd-mapper.cmd") (Join-Path $dist "payload\bin\euvd-mapper.cmd")
Copy-Item (Join-Path $Root "bootstrap_pip.py") (Join-Path $dist "payload\bootstrap_pip.py")
[IO.File]::WriteAllBytes((Join-Path $dist "payload\git-sha.txt"), [Text.Encoding]::ASCII.GetBytes($Sha + "`r`n"))
foreach ($name in @("install.ps1", "uninstall.ps1", "Invoke-Native.ps1", "README.txt", "PATCH.txt")) {
    Copy-Item (Join-Path $Root $name) (Join-Path $dist $name)
}

$authored = @(Get-ChildItem $dist -Recurse -File | Where-Object { $_.Extension -in @(".ps1", ".cmd", ".py", ".txt") })
foreach ($file in $authored) { Assert-TextFile $file.FullName }
Write-Output "Package ready: $dist"
Get-ChildItem $dist -Recurse -File | ForEach-Object {
    $_.FullName.Substring($dist.Length + 1)
}
exit 0
