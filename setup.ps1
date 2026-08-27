$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Add GEMINI_API_KEY before running a live article." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "1. Put your Gemini key in .env"
Write-Host "2. Run: python -m white_rabbit doctor"
Write-Host '3. Run: python -m white_rabbit run "YOUR TOPIC" --project first_test'
