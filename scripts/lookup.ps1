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
$ua = "euvd-mapper/0.2 (https://github.com/rkosinski941/euvd-mapper)"

# /api/search page is 0-based and size max is 100 (checked live).
# Page 0 of Apache Tomcat returns 100, page 1 the rest, page 2 empty.
if ($Size -gt 100) { $Size = 100 }
if ($Size -lt 1) { $Size = 100 }

function Get-EuvdJson {
  param([string]$Url)
  $attempt = 0
  while ($attempt -lt 4) {
    $attempt++
    $tmp = New-TemporaryFile
    try {
      $code = (& curl.exe -sS -A $ua -H "Accept: application/json" -o $tmp.FullName -w "%{http_code}" $Url)
      $code = "$code".Trim()
      if ($code -eq "200") {
        $text = [System.IO.File]::ReadAllText($tmp.FullName)
        if (-not $text) { throw "Empty response from EUVD API" }
        return ($text | ConvertFrom-Json)
      }
      if ($code -eq "429" -or $code.StartsWith("5")) {
        Start-Sleep -Seconds ([Math]::Min(16, [int][Math]::Pow(2, $attempt)))
        continue
      }
      throw "EUVD HTTP $code for $Url"
    } finally {
      Remove-Item -Force $tmp.FullName -ErrorAction SilentlyContinue
    }
  }
  throw "EUVD request failed after retries: $Url"
}

$seen = @{}
$all = New-Object System.Collections.Generic.List[object]
$total = $null
for ($page = 0; $page -lt $MaxPages; $page++) {
  $pairs = @(
    "product=$([uri]::EscapeDataString($Product))",
    "size=$Size",
    "page=$page"
  )
  if ($Vendor) { $pairs += "vendor=$([uri]::EscapeDataString($Vendor))" }
  $url = "$base`?$($pairs -join '&')"
  Write-Host "GET $url"
  $json = Get-EuvdJson $url
  if ($null -eq $total -and $null -ne $json.total) { $total = [int]$json.total }
  if ($null -eq $json.items) { break }
  $batch = @($json.items)
  $added = 0
  foreach ($item in $batch) {
    if ($null -eq $item) { continue }
    $id = [string]$item.id
    if (-not $id -or $seen.ContainsKey($id)) { continue }
    $seen[$id] = $true
    $all.Add($item) | Out-Null
    $added++
  }
  if ($batch.Count -eq 0 -or $added -eq 0) { break }
  if ($null -ne $total -and $all.Count -ge $total) { break }
  Start-Sleep -Milliseconds 300
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
