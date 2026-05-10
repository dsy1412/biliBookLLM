@echo off
cd /d "%~dp0"
if not exist "node_modules\electron" (
  echo First-time setup is required. Running desktop bootstrap...
  powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap-desktop.ps1"
  if errorlevel 1 (
    echo Bootstrap failed.
    pause
    exit /b 1
  )
)
npm run desktop
