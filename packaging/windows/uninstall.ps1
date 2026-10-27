# Remove only the files and folders this installer added.
[CmdletBinding()]
param(
    [string]$InstallRoot = ""
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

function Assert-SafeRoot {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    if ($full.Length -lt 8) { throw "Install root is too short: $full" }
    $leaf = Split-Path $full -Leaf
    if ($leaf -notmatch "^EUVD-mapper") { throw "Refusing to uninstall: $full" }
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramW6432) | Where-Object { $_ }
    foreach ($root in $roots) {
        $prefix = [IO.Path]::GetFullPath($root).TrimEnd("\") + "\"
        if ($full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to uninstall under Program Files: $full"
        }
    }
    return $full.TrimEnd("\")
}

if (-not $InstallRoot) { $InstallRoot = $PSScriptRoot }
$InstallRoot = Assert-SafeRoot $InstallRoot
$recordPath = Join-Path $InstallRoot "install-record.txt"
if (-not (Test-Path $recordPath)) { throw "No install-record.txt in $InstallRoot" }
$prefix = $InstallRoot + "\"
$shortcut = ""
$files = New-Object System.Collections.Generic.List[string]
$dirs = New-Object System.Collections.Generic.List[string]
foreach ($line in @(Get-Content -Path $recordPath)) {
    if ($line.StartsWith("shortcut=")) { $shortcut = $line.Substring(9) }
    elseif ($line.StartsWith("file=")) { $files.Add($line.Substring(5)) }
    elseif ($line.StartsWith("dir=")) { $dirs.Add($line.Substring(4)) }
}
foreach ($rel in $files) {
    if ([IO.Path]::IsPathRooted($rel)) { throw "Refusing absolute record path: $rel" }
    $full = [IO.Path]::GetFullPath((Join-Path $InstallRoot $rel))
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside install root: $rel"
    }
    if (Test-Path $full) { Remove-Item -Path $full -Force }
}
foreach ($dir in $dirs) {
    if ($dir -match "[\\/]" -or $dir -eq "." -or $dir -eq "..") { throw "Refusing directory entry: $dir" }
    $full = Join-Path $InstallRoot $dir
    $fullResolved = [IO.Path]::GetFullPath($full)
    if (-not $fullResolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing directory outside install root: $dir"
    }
    if (Test-Path $fullResolved) { Remove-Item -Path $fullResolved -Recurse -Force }
}
if ($shortcut) {
    $shortcutFull = [IO.Path]::GetFullPath($shortcut)
    if (Test-Path $shortcutFull) { Remove-Item -Path $shortcutFull -Force }
    $parent = Split-Path $shortcutFull -Parent
    if ((Split-Path $parent -Leaf) -eq "EUVD-mapper" -and (Test-Path $parent)) {
        $left = @(Get-ChildItem -Path $parent -Force -ErrorAction SilentlyContinue)
        if ($left.Count -eq 0) { Remove-Item -Path $parent -Force }
    }
}
$pycaches = @(Get-ChildItem -Path $InstallRoot -Recurse -Directory -Force -Filter "__pycache__" -ErrorAction SilentlyContinue)
foreach ($pycache in ($pycaches | Sort-Object FullName -Descending)) {
    $pycFull = [IO.Path]::GetFullPath($pycache.FullName)
    if (-not $pycFull.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { continue }
    if (Test-Path $pycFull) { Remove-Item -Path $pycFull -Recurse -Force }
}
if (Test-Path $InstallRoot) {
    $dirsLeft = @(Get-ChildItem -Path $InstallRoot -Recurse -Directory -Force -ErrorAction SilentlyContinue)
    foreach ($dir in ($dirsLeft | Sort-Object FullName -Descending)) {
        $content = @(Get-ChildItem -Path $dir.FullName -Force -ErrorAction SilentlyContinue)
        if ($content.Count -eq 0) { Remove-Item -Path $dir.FullName -Force }
    }
    $rootLeft = @(Get-ChildItem -Path $InstallRoot -Force -ErrorAction SilentlyContinue)
    if ($rootLeft.Count -eq 0) { Remove-Item -Path $InstallRoot -Force }
}
Write-Output "Uninstalled $InstallRoot"
exit 0
