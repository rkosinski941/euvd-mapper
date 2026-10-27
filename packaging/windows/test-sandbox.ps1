# Install and test only under the sandbox profile. Never the real profile.
Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"
$Root = Join-Path $env:TEMP "euvd-mapper-build"
$Pkg = Join-Path $Root "dist\EUVD-mapper"
$ProfileRoot = Join-Path $Root "profile"
$Install = Join-Path $ProfileRoot "EUVD-mapper"
$Menu = Join-Path $ProfileRoot "StartMenu"
$EmbedRoot = Join-Path $ProfileRoot "EUVD-mapper-embed"
$EmbedMenu = Join-Path $ProfileRoot "StartMenuEmbed"
$Log = Join-Path $Root "test-result.txt"
Set-Location $Root
. (Join-Path $Root "Invoke-Native.ps1")

function Say {
    param([string]$Message)
    $line = (Get-Date -Format "o") + " " + $Message
    Add-Content -Path $Log -Value $line
    Write-Output $line
}

function Invoke-Install {
    param([string]$Target, [string]$StartMenu, [switch]$ForceEmbed)
    if ($Target.IndexOf("euvd-mapper-build") -lt 0) { throw "Refusing install outside the sandbox: $Target" }
    $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Pkg "install.ps1"), "-InstallRoot", $Target, "-StartMenu", $StartMenu)
    if ($ForceEmbed) { $args += "-ForceEmbed" }
    Invoke-Native -FilePath "powershell.exe" -ArgumentList $args
}

function Invoke-Uninstall {
    param([string]$Target)
    if ($Target.IndexOf("euvd-mapper-build") -lt 0) { throw "Refusing uninstall outside the sandbox: $Target" }
    Invoke-Native -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        (Join-Path $Pkg "uninstall.ps1"), "-InstallRoot", $Target
    )
}

if (Test-Path $Log) { Remove-Item $Log -Force }
$realApp = Join-Path $env:LOCALAPPDATA "EUVD-mapper"
$realMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\EUVD-mapper"
$realBefore = Test-Path $realApp
$menuBefore = Test-Path $realMenu
$realStamp = $null
$realCount = -1
if ($realBefore) {
    $realStamp = (Get-Item $realApp).LastWriteTimeUtc.Ticks
    $realCount = @(Get-ChildItem $realApp -Recurse -File -ErrorAction SilentlyContinue).Count
}
Say "REAL_BEFORE app=$realBefore menu=$menuBefore count=$realCount"

if (Test-Path $ProfileRoot) { Remove-Item $ProfileRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $ProfileRoot | Out-Null

Say "INSTALL_VENV begin"
Invoke-Install -Target $Install -StartMenu $Menu
Say "INSTALL_VENV pass"

$py = Join-Path $Install "venv\Scripts\python.exe"
$app = Join-Path $Install "app"
Push-Location $app
try {
    Invoke-Native -FilePath $py -ArgumentList @("-m", "unittest", "discover", "-s", "tests")
} finally {
    Pop-Location
}
Say "UNITTEST_VENV pass"

$work = Join-Path $Root "work"
if (Test-Path $work) { Remove-Item $work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $work | Out-Null
$inputBook = Join-Path $work "report.xlsx"
$outputBook = Join-Path $work "report-EUVD.xlsx"
Invoke-Native -FilePath $py -ArgumentList @((Join-Path $Root "check_workbook.py"), "build", $inputBook)
$beforeHash = (Get-FileHash -Algorithm SHA256 -Path $inputBook).Hash
Invoke-Native -FilePath $py -ArgumentList @(
    "-m", "euvd_mapper", "enrich-xlsx", $inputBook, "-o", $outputBook,
    "--cache-dir", (Join-Path $Install "cache"), "--offline"
)
$afterHash = (Get-FileHash -Algorithm SHA256 -Path $inputBook).Hash
if ($beforeHash -ne $afterHash) { throw "Input workbook bytes changed" }
if (-not (Test-Path $outputBook)) { throw "Expected output report-EUVD.xlsx" }
Invoke-Native -FilePath $py -ArgumentList @((Join-Path $Root "check_workbook.py"), "check", $inputBook, $outputBook)
Say "WORKBOOK pass"

$usage = & cmd.exe /c "echo.| `"$(Join-Path $Install 'bin\euvd-enrich.cmd')`""
if ($LASTEXITCODE -ne 1) { throw "Drop wrapper with no file should exit 1, got $LASTEXITCODE" }
$usageText = $usage -join " "
if ($usageText -notmatch "Drop a Black Duck") { throw "Drop wrapper usage text missing" }
Say "DROP_USAGE pass"

Invoke-Native -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $Root "excel-open.ps1"), "-Path", $outputBook
)
Say "EXCEL pass"

$cacheDir = Join-Path $Install "cache"
New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
$sentinel = Join-Path $cacheDir "sentinel.txt"
[IO.File]::WriteAllBytes($sentinel, [Text.Encoding]::ASCII.GetBytes("keep-me"))
$pyproject = Join-Path $Install "app\pyproject.toml"
$stamp = (Get-Item $pyproject).LastWriteTimeUtc.Ticks
Invoke-Install -Target $Install -StartMenu $Menu
$stamp2 = (Get-Item $pyproject).LastWriteTimeUtc.Ticks
if ($stamp -ne $stamp2) { throw "Identical file was rewritten" }
if (Test-Path (Join-Path $Install "backup")) { throw "Backup created for an identical install" }
if ((Get-Content $sentinel -Raw) -ne "keep-me") { throw "Cache sentinel changed on identical upgrade" }
Say "UPGRADE_IDENTICAL pass"

$probe = Join-Path $Pkg "payload\app\upgrade-probe.txt"
if (Test-Path $probe) { Remove-Item $probe -Force }
try {
    [IO.File]::WriteAllBytes($probe, [Text.Encoding]::ASCII.GetBytes("v1"))
    Invoke-Install -Target $Install -StartMenu $Menu
    if ((Get-Content (Join-Path $Install "app\upgrade-probe.txt") -Raw) -ne "v1") { throw "Probe v1 was not installed" }
    [IO.File]::WriteAllBytes($probe, [Text.Encoding]::ASCII.GetBytes("v2"))
    Invoke-Install -Target $Install -StartMenu $Menu
    $installedProbe = Get-Content (Join-Path $Install "app\upgrade-probe.txt") -Raw
    if ($installedProbe -ne "v2") { throw "Probe was not upgraded to v2" }
    $backed = @(Get-ChildItem (Join-Path $Install "backup") -Recurse -Filter "upgrade-probe.txt")
    if ($backed.Count -lt 1) { throw "Upgrade did not back up the replaced probe" }
    $old = Get-Content $backed[0].FullName -Raw
    if ($old -ne "v1") { throw "Backup content was $old" }
    if ((Get-Content $sentinel -Raw) -ne "keep-me") { throw "Cache sentinel lost during upgrade" }
    Say "UPGRADE_REPLACE pass"
} finally {
    if (Test-Path $probe) { Remove-Item $probe -Force }
}

$linkPath = Join-Path $Menu "EUVD-mapper\EUVD Mapper.lnk"
if (-not (Test-Path $linkPath)) { throw "Shortcut missing" }
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($linkPath)
$target = [string]$link.TargetPath
$expected = Join-Path $Install "bin\euvd-enrich.cmd"
if ($target.TrimEnd("\") -ine $expected) { throw "Shortcut target is $target" }
Say "SHORTCUT pass"

Say "INSTALL_EMBED begin"
Invoke-Install -Target $EmbedRoot -StartMenu $EmbedMenu -ForceEmbed
$embedPy = Join-Path $EmbedRoot "python\python.exe"
Push-Location (Join-Path $EmbedRoot "app")
try {
    Invoke-Native -FilePath $embedPy -ArgumentList @("-m", "unittest", "discover", "-s", "tests")
} finally {
    Pop-Location
}
Say "UNITTEST_EMBED pass"

Invoke-Uninstall -Target $Install
Invoke-Uninstall -Target $EmbedRoot
if (Test-Path $Install) { throw "Venv install root remains" }
if (Test-Path $EmbedRoot) { throw "Embed install root remains" }
if (Test-Path (Join-Path $Menu "EUVD-mapper")) { throw "Sandbox shortcut folder remains" }
if (Test-Path (Join-Path $EmbedMenu "EUVD-mapper")) { throw "Embed shortcut folder remains" }
if (Test-Path $outputBook) { Say "OUTPUT_KEPT report-EUVD.xlsx" }
Say "UNINSTALL pass"

$realAfter = Test-Path $realApp
$menuAfter = Test-Path $realMenu
if ($realAfter -ne $realBefore) { throw "Real LOCALAPPDATA\EUVD-mapper existence changed" }
if ($menuAfter -ne $menuBefore) { throw "Real Start menu EUVD-mapper existence changed" }
if ($realBefore) {
    $nowStamp = (Get-Item $realApp).LastWriteTimeUtc.Ticks
    $nowCount = @(Get-ChildItem $realApp -Recurse -File -ErrorAction SilentlyContinue).Count
    if ($nowStamp -ne $realStamp -or $nowCount -ne $realCount) {
        throw "Real install directory changed"
    }
}
Say "REAL_PROFILE_UNTOUCHED pass"
Say "ALL_PASS"
exit 0
