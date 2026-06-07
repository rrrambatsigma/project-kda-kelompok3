# load-env.ps1 — Load .env ke terminal PowerShell
# Cara pakai: . .\load-env.ps1

$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "[!] File .env tidak ditemukan!" -ForegroundColor Red
    Write-Host "    Jalankan: copy .env.example .env" -ForegroundColor Yellow
    return
}

$count = 0
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        $count++
    }
}

Write-Host "[OK] $count environment variables loaded dari .env" -ForegroundColor Green
Write-Host ""
Write-Host "  GENERATOR_PORT     = $env:GENERATOR_PORT"
Write-Host "  API_SERVER_PORT    = $env:API_SERVER_PORT"
Write-Host "  STREAM_URL         = $env:STREAM_URL"
Write-Host "  PREDICTION_POST_URL= $env:PREDICTION_POST_URL"
Write-Host "  SSE_URL            = $env:SSE_URL"
Write-Host "  PYTHONIOENCODING   = $env:PYTHONIOENCODING"
Write-Host ""
