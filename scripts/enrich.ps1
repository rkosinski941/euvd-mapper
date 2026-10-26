<#
.SYNOPSIS
  Write a copy of a BOM workbook with EUVD matches.

.DESCRIPTION
  ASCII-only wrapper around: python -m euvd_mapper enrich-xlsx
  Requires Python 3 and openpyxl. Does not overwrite the input file.
  A Black Duck project report (Bill of Materials + Vulnerabilities) gains
  EUVD Vulnerabilities and EUVD Run Summary sheets. Other workbooks gain
  EUVD columns. Pass -Sheet to force the column layout.
  Live runs cache JSON under -CacheDir and pause between API calls.

.EXAMPLE
  .\scripts\enrich.ps1 -InputPath .\report.xlsx -Out .\report-euvd.xlsx -CacheDir .\.cache\euvd-mapper

.EXAMPLE
  .\scripts\enrich.ps1 -InputPath .\examples\black-duck-sample.xlsx -Out .\examples\black-duck-sample-euvd.xlsx -CacheDir .\tests\fixtures\cache -Offline
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$InputPath,

  [string]$Out = "",

  [string]$Sheet = "",

  [string]$NameColumn = "",

  [string]$VersionColumn = "",

  [string]$PurlColumn = "",

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
if ($NameColumn) { $argList += @("--name-column", $NameColumn) }
if ($VersionColumn) { $argList += @("--version-column", $VersionColumn) }
if ($PurlColumn) { $argList += @("--purl-column", $PurlColumn) }
if ($CacheDir) { $argList += @("--cache-dir", $CacheDir) }
if ($Offline) { $argList += "--offline" }

& $runner @argList
exit $LASTEXITCODE
