$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host $Message
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Command = 'py'; Args = @('-3') }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Command = 'python'; Args = @() }
    }

    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        return @{ Command = 'python3'; Args = @() }
    }

    throw '[docker] Python was not found. Install Python 3.10+ or enable the Python launcher (`py`).'
}

Write-Step '[docker] Day 19 full Docker setup'
Write-Step '[docker] Stack: Qdrant (server) + Redis + Postgres + bge-m3 embeddings'
Write-Host ''

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw '[docker] Docker not found. Install Docker Desktop first.'
}

docker compose version | Out-Null

Write-Step '[docker] Bringing up services'
docker compose up -d

Write-Host '[docker] Waiting up to 30s for services to become healthy...'
$healthy = $false
for ($i = 1; $i -le 30; $i++) {
    $healthOutput = docker compose ps --format json 2>$null
    if ($healthOutput -match '"Health":"healthy"') {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $healthy) {
    Write-Host '[docker] Warning: services did not report healthy within 30s; continuing anyway.'
}

$python = Get-PythonCommand
$pythonCommand = $python.Command
$pythonArgs = $python.Args
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path '.venv')) {
    Write-Step '[docker] Creating venv'
    & $pythonCommand @pythonArgs -m venv .venv
}

if (-not (Test-Path $venvPython)) {
    throw "[docker] Missing venv interpreter at $venvPython"
}

Write-Step '[docker] Installing dependencies'
& $venvPython -m pip install -q -U pip
& $venvPython -m pip install -q -r requirements.txt -r requirements-full.txt

Write-Step '[docker] Converting Jupytext sources'
& $venvPython -m jupytext --to notebook --update notebooks\*.py

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    (Get-Content '.env') |
        ForEach-Object {
            $line = $_
            $line = $line -replace '^QDRANT_MODE=memory', 'QDRANT_MODE=server'
            $line = $line -replace '^EMBEDDING_BACKEND=fastembed', 'EMBEDDING_BACKEND=bge-m3'
            $line = $line -replace '^FEAST_ONLINE_STORE=sqlite', 'FEAST_ONLINE_STORE=redis'
            $line = $line -replace '^FEAST_OFFLINE_STORE=file', 'FEAST_OFFLINE_STORE=postgres'
            $line
        } |
        Set-Content '.env' -Encoding UTF8
}

Write-Step '[docker] Seeding corpus'
& $venvPython scripts\seed_corpus.py

Write-Step '[docker] Running smoke test'
& $venvPython scripts\verify_docker.py

Write-Host ''
Write-Host '[docker] Done. Services running:'
Write-Host ''
Write-Host '  Qdrant   → http://localhost:6333  (dashboard)'
Write-Host '  Redis    → redis://localhost:6379'
Write-Host '  Postgres → postgresql://feast:feast@localhost:5432/feast_offline'
Write-Host ''
Write-Host 'Activate the venv and continue:'
Write-Host ''
Write-Host '    .\.venv\Scripts\Activate.ps1'
Write-Host '    make api       # start FastAPI on :8000'
Write-Host '    make lab       # open Jupyter on :8888'
Write-Host ''
Write-Host 'Stop the stack later: docker compose down (state persists)'
Write-Host '                  or  docker compose down -v (full reset)'
