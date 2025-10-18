# run_speedlogger.ps1 (dotenv approach)
$pythonPath = "C:\Program Files\Python311\python.exe"
$scriptPath = "D:\speedtest_bundle\speedlogger.py"
$logPath = "D:\speedtest_bundle\speedlogger_run.log"
$envFile = "D:\speedtest_bundle\.env"

# Load .env file if present
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*#') { return }     # skip comments
        if ($_ -match '^\s*$') { return }     # skip empty lines
        $parts = $_ -split '=', 2
        if ($parts.Count -eq 2) {
            $name = $parts[0].Trim()
            $val  = $parts[1].Trim().Trim('"')
            if ($name -and $val) { [System.Environment]::SetEnvironmentVariable($name, $val, 'Process') }
        }
    }
}

# Ensure webhook exists now (process env)
if (-not $env:DISCORD_WEBHOOK) {
    Write-Host "ERROR: DISCORD_WEBHOOK not found (set in system env or .env). Exiting."
    Exit 1
}

Set-Location (Split-Path $scriptPath)
& $pythonPath $scriptPath 2>&1 | Out-File -FilePath $logPath -Append -Encoding utf8
Exit $LASTEXITCODE
