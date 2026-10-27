# Per-user install. No admin, no Program Files, no registry.
[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$StartMenu = "",
    [switch]$ForceEmbed
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Invoke-Native.ps1")

$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
$env:PYTHONNOUSERSITE = "1"

function Write-Ascii {
    param([string]$Path, [string]$Text)
    $parent = Split-Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $normalized = ($Text -replace "`r`n", "`n") -replace "`n", "`r`n"
    if (-not $normalized.EndsWith("`r`n")) { $normalized += "`r`n" }
    [IO.File]::WriteAllBytes($Path, [Text.Encoding]::ASCII.GetBytes($normalized))
}

function Assert-SafeRoot {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    if ($full.Length -lt 8) { throw "Install root is too short: $full" }
    $leaf = Split-Path $full -Leaf
    if ($leaf -notmatch "^EUVD-mapper") { throw "Install root must be named EUVD-mapper: $full" }
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramW6432) | Where-Object { $_ }
    foreach ($root in $roots) {
        $prefix = [IO.Path]::GetFullPath($root).TrimEnd("\") + "\"
        if ($full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to install under Program Files: $full"
        }
    }
    return $full
}

function Get-WorkingPython {
    $ordered = @("3.12", "3.13", "3.11", "3.10", "3.9")
    $candidates = New-Object System.Collections.Generic.List[string]
    $launchers = New-Object System.Collections.Generic.List[string]
    $localPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Launcher\py.exe"
    if (Test-Path $localPy) { $launchers.Add($localPy) }
    $cmd = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($cmd -and -not $launchers.Contains($cmd.Source)) { $launchers.Add($cmd.Source) }
    Push-Location $env:TEMP
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        foreach ($launcher in $launchers) {
            foreach ($ver in $ordered) {
                $arg = "-" + $ver
                $output = & $launcher $arg -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $output) {
                    $path = ([string]($output | Select-Object -Last 1)).Trim()
                    if ($path -and -not $candidates.Contains($path)) { $candidates.Add($path) }
                }
            }
        }
        $base = Join-Path $env:LOCALAPPDATA "Programs\Python"
        foreach ($folder in @("Python312", "Python313", "Python311", "Python310", "Python39")) {
            $exe = Join-Path $base ($folder + "\python.exe")
            if ((Test-Path $exe) -and -not $candidates.Contains($exe)) { $candidates.Add($exe) }
        }
        foreach ($exe in $candidates) {
            & $exe -c "import encodings,sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
            if ($LASTEXITCODE -eq 0) { return $exe }
        }
    } finally {
        $ErrorActionPreference = $previous
        Pop-Location
    }
    return $null
}

function Get-WheelsHash {
    param([string]$Dir)
    $files = @(Get-ChildItem $Dir -Filter *.whl | Sort-Object Name)
    $builder = New-Object System.Text.StringBuilder
    foreach ($file in $files) {
        $hash = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash
        [void]$builder.AppendLine($file.Name + " " + $hash)
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    $bytes = [Text.Encoding]::ASCII.GetBytes($builder.ToString())
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "")
}

function Copy-PayloadFile {
    param([string]$Source, [string]$DestRel)
    $dest = Join-Path $InstallRoot $DestRel
    $parent = Split-Path $dest -Parent
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    if (Test-Path $dest) {
        $srcHash = (Get-FileHash -Algorithm MD5 -Path $Source).Hash
        $dstHash = (Get-FileHash -Algorithm MD5 -Path $dest).Hash
        if ($srcHash -eq $dstHash) { return }
        if (-not $script:DidBackup) {
            New-Item -ItemType Directory -Force -Path $script:BackupRoot | Out-Null
            $script:DidBackup = $true
        }
        $backup = Join-Path $script:BackupRoot $DestRel
        $backupParent = Split-Path $backup -Parent
        if (-not (Test-Path $backupParent)) {
            New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
        }
        Copy-Item -Path $dest -Destination $backup -Force
    }
    Copy-Item -Path $Source -Destination $dest -Force
}

function Copy-Tree {
    param([string]$SourceDir, [string]$DestRel)
    $base = (Resolve-Path $SourceDir).Path
    if (-not $base.EndsWith("\")) { $base = $base + "\" }
    $files = @(Get-ChildItem -Path $SourceDir -Recurse -File)
    foreach ($file in $files) {
        if ($file.FullName -match "\\__pycache__\\|\\.pyc$") { continue }
        $rel = $file.FullName.Substring($base.Length)
        Copy-PayloadFile -Source $file.FullName -DestRel (Join-Path $DestRel $rel)
    }
}

function Move-RuntimeAside {
    param([string]$Name)
    $path = Join-Path $InstallRoot $Name
    if (-not (Test-Path $path)) { return }
    if (-not $script:DidBackup) {
        New-Item -ItemType Directory -Force -Path $script:BackupRoot | Out-Null
        $script:DidBackup = $true
    }
    $dest = Join-Path $script:BackupRoot $Name
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    Move-Item -Path $path -Destination $dest
}

function Install-PrivateVenv {
    param([string]$BasePython, [string]$WheelsHash)
    $markerPath = Join-Path $InstallRoot "runtime-marker.txt"
    $wanted = "kind=venv`r`nbase=$BasePython`r`nwheels=$WheelsHash"
    $venv = Join-Path $InstallRoot "venv"
    $venvPy = Join-Path $venv "Scripts\python.exe"
    if ((Test-Path $markerPath) -and (Test-Path $venvPy)) {
        $current = [IO.File]::ReadAllText($markerPath).Trim()
        if ($current -eq $wanted.Replace("`r`n", "`n").Trim() -or $current -eq $wanted.Trim()) {
            Write-Host "Keeping existing venv"
            return $venvPy
        }
    }
    Move-RuntimeAside "venv"
    Move-RuntimeAside "python"
    Write-Host "Creating venv from $BasePython"
    Invoke-Native -FilePath $BasePython -ArgumentList @("-m", "venv", $venv)
    $wheels = Join-Path $InstallRoot "wheels"
    Invoke-Native -FilePath $venvPy -ArgumentList @(
        "-m", "pip", "install", "--no-index", "--find-links", $wheels,
        "--disable-pip-version-check", "openpyxl==3.1.5", "tzdata==2026.5", "euvd-mapper==0.2.0"
    )
    Invoke-Native -FilePath $venvPy -ArgumentList @(
        "-c", "import openpyxl,euvd_mapper; raise SystemExit(0 if openpyxl.__version__=='3.1.5' else 1)"
    )
    Write-Ascii -Path $markerPath -Text $wanted
    return $venvPy
}

function Install-EmbedPython {
    param([string]$ZipPath, [string]$WheelsHash)
    $zipHash = (Get-FileHash -Algorithm SHA256 -Path $ZipPath).Hash
    $markerPath = Join-Path $InstallRoot "runtime-marker.txt"
    $wanted = "kind=embed`r`nzip=$zipHash`r`nwheels=$WheelsHash"
    $dest = Join-Path $InstallRoot "python"
    $exe = Join-Path $dest "python.exe"
    if ((Test-Path $markerPath) -and (Test-Path $exe)) {
        $current = [IO.File]::ReadAllText($markerPath).Trim()
        if ($current -eq $wanted.Trim()) {
            Write-Host "Keeping existing embeddable Python"
            return $exe
        }
    }
    Move-RuntimeAside "python"
    Move-RuntimeAside "venv"
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $dest)
    $pth = @(Get-ChildItem $dest -Filter "python*._pth")
    if ($pth.Count -ne 1) { throw "Expected one python*._pth in the embeddable runtime" }
    $zipLine = "python312.zip"
    foreach ($line in @(Get-Content $pth[0].FullName)) {
        $trim = $line.Trim()
        if ($trim -like "python*.zip") { $zipLine = $trim }
    }
    $pthText = $zipLine + "`r`n.`r`nLib\site-packages`r`n`r`nimport site`r`n"
    [IO.File]::WriteAllBytes($pth[0].FullName, [Text.Encoding]::ASCII.GetBytes($pthText))
    New-Item -ItemType Directory -Force -Path (Join-Path $dest "Lib\site-packages") | Out-Null
    $bootstrap = Join-Path $InstallRoot "bootstrap_pip.py"
    $wheels = Join-Path $InstallRoot "wheels"
    Invoke-Native -FilePath $exe -ArgumentList @($bootstrap, $wheels)
    Invoke-Native -FilePath $exe -ArgumentList @(
        "-c", "import openpyxl,euvd_mapper; raise SystemExit(0 if openpyxl.__version__=='3.1.5' else 1)"
    )
    Write-Ascii -Path $markerPath -Text $wanted
    return $exe
}

if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA "EUVD-mapper" }
if (-not $StartMenu) {
    $StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
}
$InstallRoot = Assert-SafeRoot $InstallRoot
$Payload = Join-Path $PSScriptRoot "payload"
if (-not (Test-Path (Join-Path $Payload "wheels"))) { throw "Missing payload\wheels" }
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

$script:BackupRoot = Join-Path $InstallRoot ("backup\" + [DateTime]::UtcNow.ToString("yyyyMMddHHmmss"))
$script:DidBackup = $false

Copy-Tree -SourceDir (Join-Path $Payload "app") -DestRel "app"
Copy-Tree -SourceDir (Join-Path $Payload "wheels") -DestRel "wheels"
Copy-Tree -SourceDir (Join-Path $Payload "bin") -DestRel "bin"
Copy-PayloadFile -Source (Join-Path $PSScriptRoot "uninstall.ps1") -DestRel "uninstall.ps1"
Copy-PayloadFile -Source (Join-Path $PSScriptRoot "Invoke-Native.ps1") -DestRel "Invoke-Native.ps1"
Copy-PayloadFile -Source (Join-Path $Payload "bootstrap_pip.py") -DestRel "bootstrap_pip.py"
Copy-PayloadFile -Source (Join-Path $Payload "git-sha.txt") -DestRel "git-sha.txt"

$wheelsHash = Get-WheelsHash (Join-Path $InstallRoot "wheels")
if ($ForceEmbed) {
    $python = Install-EmbedPython -ZipPath (Join-Path $Payload "python-3.12.10-embed-amd64.zip") -WheelsHash $wheelsHash
    $pythonKind = "embed"
} else {
    $base = Get-WorkingPython
    if ($base) {
        $python = Install-PrivateVenv -BasePython $base -WheelsHash $wheelsHash
        $pythonKind = "venv"
    } else {
        Write-Host "No working Python 3.9+ found. Using the bundled runtime."
        $python = Install-EmbedPython -ZipPath (Join-Path $Payload "python-3.12.10-embed-amd64.zip") -WheelsHash $wheelsHash
        $pythonKind = "embed"
    }
}

$version = & $python -c "import sys; print(sys.version.split()[0])"
if ($LASTEXITCODE -ne 0) { throw "Could not read the private Python version" }
$version = ([string]($version | Select-Object -Last 1)).Trim()

$menuDir = Join-Path $StartMenu "EUVD-mapper"
New-Item -ItemType Directory -Force -Path $menuDir | Out-Null
$shortcut = Join-Path $menuDir "EUVD Mapper.lnk"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = Join-Path $InstallRoot "bin\euvd-enrich.cmd"
$link.WorkingDirectory = Join-Path $InstallRoot "bin"
$link.Description = "Enrich a Black Duck report with EUVD sheets"
$link.Save()

$gitSha = ([IO.File]::ReadAllText((Join-Path $InstallRoot "git-sha.txt"))).Trim()
$header = @(
    "git-sha: $gitSha",
    "package: euvd-mapper 0.2.0",
    "openpyxl: 3.1.5",
    "python: $version ($pythonKind)",
    "hashes: sha256 of installed files except manifest.txt and install-record.txt",
    "cache and backup directories are not hashed"
)
$lines = New-Object System.Collections.Generic.List[string]
foreach ($item in $header) { $lines.Add($item) }
$skip = @("cache", "backup")
$files = @(Get-ChildItem $InstallRoot -Recurse -File | Sort-Object FullName)
foreach ($file in $files) {
    $rel = $file.FullName.Substring($InstallRoot.Length).TrimStart("\")
    $top = $rel.Split("\")[0]
    if ($skip -contains $top) { continue }
    if ($rel -eq "manifest.txt" -or $rel -eq "install-record.txt") { continue }
    $hash = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash.ToLower()
    $lines.Add($rel.Replace("\", "/") + " " + $hash)
}
Write-Ascii -Path (Join-Path $InstallRoot "manifest.txt") -Text ($lines -join "`n")

$record = New-Object System.Collections.Generic.List[string]
$record.Add("shortcut=" + $shortcut)
$record.Add("dir=venv")
$record.Add("dir=python")
$record.Add("dir=cache")
$record.Add("dir=backup")
$listed = @(Get-ChildItem $InstallRoot -Recurse -File | Sort-Object FullName)
foreach ($file in $listed) {
    $rel = $file.FullName.Substring($InstallRoot.Length).TrimStart("\")
    $top = $rel.Split("\")[0]
    if ($skip -contains $top) { continue }
    if ($top -eq "venv" -or $top -eq "python") { continue }
    $record.Add("file=" + $rel)
}
if (-not ($record -contains "file=install-record.txt")) { $record.Add("file=install-record.txt") }
Write-Ascii -Path (Join-Path $InstallRoot "install-record.txt") -Text ($record -join "`n")
Write-Host "Installed $InstallRoot ($pythonKind $version)"
exit 0
