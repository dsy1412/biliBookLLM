$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repoRoot "apps\api"
$webDir = Join-Path $repoRoot "apps\web"
$venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"

Write-Host "[1/4] Creating Python virtual environment if needed..."
if (-not (Test-Path $venvPython)) {
  Push-Location $apiDir
  try {
    python -m venv .venv
  }
  finally {
    Pop-Location
  }
}

Write-Host "[2/4] Installing backend dependencies..."
Push-Location $apiDir
try {
  & $venvPython -m pip install -e ".[dev]"
}
finally {
  Pop-Location
}

Write-Host "[3/4] Installing desktop and frontend dependencies..."
Push-Location $repoRoot
try {
    npm install
    Push-Location $webDir
    try {
      npm install
    }
    finally {
      Pop-Location
    }
}
finally {
  Pop-Location
}

Write-Host "[4/4] Building the web app for faster desktop startup..."
Push-Location $webDir
try {
  npm run build
}
finally {
  Pop-Location
}

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Launch later with: launch-desktop.bat"
