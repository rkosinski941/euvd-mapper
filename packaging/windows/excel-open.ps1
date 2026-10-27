# Open a workbook in Excel, read the sheet names, and close only an instance we started.
param(
    [Parameter(Mandatory = $true)][string]$Path
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Path)) { throw "Workbook not found: $Path" }

function Invoke-Excel {
    param([scriptblock]$Action)
    for ($try = 1; $try -le 40; $try++) {
        try {
            return (& $Action)
        } catch [System.Runtime.InteropServices.COMException] {
            if ($try -eq 40) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Excel did not accept a call"
}

$before = @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$excel = $null
$workbook = $null
$created = @()
try {
    $excel = New-Object -ComObject Excel.Application
    Start-Sleep -Seconds 1
    $after = @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $created = @($after | Where-Object { $before -notcontains $_ })
    Invoke-Excel { $excel.Visible = $false }
    Invoke-Excel { $excel.DisplayAlerts = $false }
    Invoke-Excel { $excel.EnableEvents = $false }
    Invoke-Excel { $excel.AskToUpdateLinks = $false }
    Invoke-Excel { $excel.Interactive = $false }
    $workbook = Invoke-Excel { $excel.Workbooks.Open($Path, 0, $true) }
    $names = Invoke-Excel {
        $found = New-Object System.Collections.Generic.List[string]
        $count = [int]$workbook.Worksheets.Count
        for ($index = 1; $index -le $count; $index++) {
            $found.Add([string]$workbook.Worksheets.Item($index).Name)
        }
        return ,$found
    }
    if ($names.Count -lt 1 -or [string]::IsNullOrWhiteSpace($names[0])) {
        throw "Excel opened the workbook but did not return sheet names"
    }
    Write-Output ("EXCEL_SHEETS " + ($names -join " | "))
    Invoke-Excel { $workbook.Close($false) | Out-Null }
    $workbook = $null
    if ($created.Count -ge 1) {
        Invoke-Excel { $excel.Quit() | Out-Null }
    } else {
        Write-Output "EXCEL_ATTACHED_EXISTING_NO_QUIT"
    }
    $excel = $null
} finally {
    if ($workbook -ne $null) {
        try { $workbook.Close($false) | Out-Null } catch { }
    }
    if ($excel -ne $null -and $created.Count -ge 1) {
        try { $excel.Quit() | Out-Null } catch { }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
Start-Sleep -Seconds 1
$still = @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$left = @($still | Where-Object { $before -notcontains $_ })
if ($left.Count -gt 0) {
    foreach ($procId in $left) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
    $still = @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $left = @($still | Where-Object { $before -notcontains $_ })
    if ($left.Count -gt 0) { throw ("Excel process still running: " + ($left -join ",")) }
    Write-Output "EXCEL_FORCE_CLOSED"
}
Write-Output "EXCEL_CLOSED"
exit 0
