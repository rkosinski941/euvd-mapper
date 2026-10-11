<#
.SYNOPSIS
  Add EUVD columns to a BOM workbook.

.DESCRIPTION
  ASCII-only wrapper around: python -m euvd_mapper enrich-xlsx
  Requires Python 3 and openpyxl. Does not overwrite the input file.

.EXAMPLE
  .\scripts\enrich.ps1 -InputPath .\examples\black-duck-sample.xlsx -Out .\examples\black-duck-sample-euvd.xlsx -Offline
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$InputPath,

  [string]$Out = "",

  [string]$Sheet = "",

  [string]$CacheDir = "",

  [switch]$Offline
)

$ErrorActionPreference = "Stop"

$runner = $null
$prefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
  $runner = "py"
  $prefix = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $runner = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  $runner = "python3"
} else {
  throw "Python 3 is required to run euvd_mapper."
}

$argList = $prefix + @("-m", "euvd_mapper", "enrich-xlsx", $InputPath)
if ($Out) { $argList += @("-o", $Out) }
if ($Sheet) { $argList += @("--sheet", $Sheet) }
if ($CacheDir) { $argList += @("--cache-dir", $CacheDir) }
if ($Offline) { $argList += "--offline" }

& $runner @argList
exit $LASTEXITCODE
