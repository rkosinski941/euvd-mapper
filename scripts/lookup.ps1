<#
.SYNOPSIS
  Query ENISA EUVD for a product (and optional vendor/version) and write JSON.

.EXAMPLE
  .\scripts\lookup.ps1 -Product "Apache Tomcat" -Version "9.0.20"
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$Product,

  [string]$Vendor = "",

  [string]$Version = "",

  [string]$Out = "",

  [int]$Size = 100,

  [int]$MaxPages = 5
)

$ErrorActionPreference = "Stop"
$base = "https://euvdservices.enisa.europa.eu/api/search"
$headers = @{
  Accept     = "application/json"
  "User-Agent" = "euvd-mapper/0.1 (https://github.com/rkosinski941/euvd-mapper)"
}

$all = @()
$total = $null
for ($page = 0; $page -lt $MaxPages; $page++) {
  $qs = [System.Web.HttpUtility]::ParseQueryString("")
  # ParseQueryString needs System.Web; build the query by hand instead.
  $pairs = @(
    "product=$([uri]::EscapeDataString($Product))",
    "size=$Size",
    "page=$page"
  )
  if ($Vendor) { $pairs += "vendor=$([uri]::EscapeDataString($Vendor))" }
  $url = "$base`?$($pairs -join '&')"
  Write-Host "GET $url"
  $resp = curl.exe -sS -A $headers["User-Agent"] -H "Accept: application/json" $url
  if (-not $resp) { throw "Empty response from EUVD API" }
  $json = $resp | ConvertFrom-Json
  if ($null -eq $total) { $total = $json.total }
  if (-not $json.items -or $json.items.Count -eq 0) { break }
  $all += $json.items
  if ($all.Count -ge [int]$total) { break }
}

$payload = [ordered]@{
  queriedAt     = (Get-Date).ToUniversalTime().ToString("o")
  product       = $Product
  vendor        = $Vendor
  version       = $Version
  source        = $base
  totalReported = $total
  itemCount     = $all.Count
  items         = $all
}

$text = $payload | ConvertTo-Json -Depth 12
if ($Out) {
  $dir = Split-Path -Parent $Out
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -Path $Out -Value $text -Encoding utf8
  Write-Host "Wrote $Out ($($all.Count) of $total)"
} else {
  $text
}
