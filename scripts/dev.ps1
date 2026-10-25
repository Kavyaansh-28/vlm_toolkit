# Windows launcher: FastAPI backend (port 8010) + Next.js dashboard (port 3000) in two windows.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$apiPort = if ($env:VLM_API_PORT) { $env:VLM_API_PORT } else { "8010" }
$webPort = if ($env:VLM_WEB_PORT) { $env:VLM_WEB_PORT } else { "3000" }

Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", "& '$python' -m uvicorn api.server:app --host 127.0.0.1 --port $apiPort"
Start-Process powershell -WorkingDirectory (Join-Path $root "frontend") -ArgumentList "-NoExit", "-Command", "corepack pnpm install; corepack pnpm dev --port $webPort"
Write-Host "Backend:   http://127.0.0.1:$apiPort/health"
Write-Host "Dashboard: http://127.0.0.1:$webPort"
