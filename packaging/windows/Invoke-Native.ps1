# Run a native command and fail when it returns a non-zero exit code.
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @ArgumentList | Out-Host
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            $shown = $ArgumentList -join " "
            throw "Command failed ($LASTEXITCODE): $FilePath $shown"
        }
    } finally {
        $ErrorActionPreference = $previous
    }
}
