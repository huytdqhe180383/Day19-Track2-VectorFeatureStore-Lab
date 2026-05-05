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

    throw '[lite] Python was not found. Install Python 3.10+ or enable the Python launcher (`py`).'
}

Write-Step '[lite] Day 19 lightweight setup'
Write-Step '[lite] Stack: fastembed + qdrant-client[memory] + rank-bm25 + feast(sqlite) + FastAPI'
Write-Host ''

$python = Get-PythonCommand
$pythonCommand = $python.Command
$pythonArgs = $python.Args
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

Write-Step '[lite] Python detected'

if (-not (Test-Path '.venv')) {
    Write-Step '[lite] Creating venv'
    & $pythonCommand @pythonArgs -m venv .venv
}

if (-not (Test-Path $venvPython)) {
    throw "[lite] Missing venv interpreter at $venvPython"
}

Write-Step '[lite] Installing dependencies'
& $venvPython -m pip install -q -U pip
& $venvPython -m pip install -q -r requirements.txt

Write-Step '[lite] Converting Jupytext sources'
& $venvPython -m jupytext --to notebook --update notebooks\*.py

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
}

Write-Step '[lite] Seeding corpus'
& $venvPython scripts\seed_corpus.py

Write-Step '[lite] Running smoke test'
& $venvPython scripts\verify_lite.py

Write-Host ''
Write-Host '[lite] Done. Activate the venv and start working:'
Write-Host ''
Write-Host '    .\.venv\Scripts\Activate.ps1'
Write-Host '    make api       # start FastAPI on :8000'
Write-Host '    make lab       # open Jupyter on :8888'
Write-Host '    make benchmark # Precision@10 + latency table'
Write-Host ''
Write-Host 'Tip: read VIBE-CODING.md before starting NB1 — it tells you what to delegate'
Write-Host 'to your AI assistant and what to think through yourself.'
