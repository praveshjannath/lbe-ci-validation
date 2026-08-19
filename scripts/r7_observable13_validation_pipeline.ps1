$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RunRoot = Join-Path $Root '.observable13_pipeline'
$Log = Join-Path $RunRoot 'observable13-validation.log'

if (Test-Path $RunRoot) {
    Remove-Item $RunRoot -Recurse -Force
}
New-Item -ItemType Directory -Force $RunRoot | Out-Null
Start-Transcript -Path $Log -Force | Out-Null

$Stage = 0
$Wheel = $null
$Venv = $null
$Python = $null
$Lbe = $null

function Invoke-Stage {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Body
    )

    $script:Stage += 1
    Write-Output ''
    Write-Output '================================================================'
    Write-Output "STAGE $script:Stage :: $Name"
    Write-Output "START=$(Get-Date -Format o)"
    Write-Output '================================================================'

    try {
        & $Body
        if ($LASTEXITCODE -ne 0) {
            throw "EXIT_CODE=$LASTEXITCODE"
        }
        Write-Output 'STAGE_RESULT=PASS'
        Write-Output "END=$(Get-Date -Format o)"
    }
    catch {
        Write-Output 'STAGE_RESULT=FAIL'
        Write-Output "FAILED_STAGE=$script:Stage"
        Write-Output "FAILED_NAME=$Name"
        Write-Output "ERROR=$($_.Exception.Message)"
        Write-Output "LOG=$Log"
        throw
    }
}

try {
    Push-Location $Root
    try {
        Invoke-Stage 'PULL_ORIGIN_MAIN' {
            git pull --ff-only origin main
        }

        Invoke-Stage 'AUTHORITY_AND_GATE' {
            $Branch = (git branch --show-current).Trim()
            git fetch origin --prune
            $Head = (git rev-parse HEAD).Trim()
            $Origin = (git rev-parse origin/main).Trim()
            Write-Output "BRANCH=$Branch"
            Write-Output "HEAD=$Head"
            Write-Output "ORIGIN_MAIN=$Origin"
            if ($Branch -ne 'main') { throw "UNEXPECTED_BRANCH=$Branch" }
            if ($Head -ne $Origin) { throw 'HEAD_ORIGIN_MAIN_MISMATCH' }
            python scripts/check-implementation-gate.py
        }

        Invoke-Stage 'BUILD_REPAIRED_WHEEL' {
            $WheelDir = Join-Path $RunRoot 'wheel'
            New-Item -ItemType Directory -Force $WheelDir | Out-Null
            python -m pip wheel . --no-deps --no-build-isolation --wheel-dir $WheelDir
            $script:Wheel = (Get-ChildItem $WheelDir -Filter '*.whl' | Select-Object -First 1).FullName
            if (-not $script:Wheel) { throw 'WHEEL_NOT_CREATED' }
            Write-Output "WHEEL=$script:Wheel"
            Get-Item $script:Wheel | Select-Object Name, Length
        }

        Invoke-Stage 'WHEEL_CONTENT_PROOF' {
            $Check = @'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
deps = [n for n in names if '/cline_worker/node_modules/' in n]
agents = [n for n in names if '/cline_worker/node_modules/@cline/agents/' in n]
worker = any(n.endswith('/cline_worker/worker.mjs') for n in names)
agentpkg = any(n.endswith('/cline_worker/node_modules/@cline/agents/package.json') for n in names)
schema = any(n.endswith('/memory/memory_schema.sql') for n in names)
print(f'DEPENDENCY_FILES={len(deps)}')
print(f'CLINE_AGENTS_FILES={len(agents)}')
print(f'HAS_WORKER={worker}')
print(f'HAS_AGENT_PACKAGE={agentpkg}')
print(f'HAS_MEMORY_SCHEMA={schema}')
if not (worker and agentpkg and schema and deps):
    raise SystemExit(2)
'@
            $CheckPath = Join-Path $RunRoot 'check_wheel.py'
            Set-Content $CheckPath $Check -Encoding utf8
            python $CheckPath $script:Wheel
        }

        Invoke-Stage 'CREATE_FRESH_ISOLATED_VENV' {
            $script:Venv = Join-Path $RunRoot 'venv'
            python -m venv $script:Venv
            $script:Python = Join-Path $script:Venv 'Scripts\python.exe'
            $script:Lbe = Join-Path $script:Venv 'Scripts\lbe.exe'
            if (-not (Test-Path $script:Python)) { throw 'VENV_PYTHON_MISSING' }
        }

        Invoke-Stage 'INSTALL_EXACT_WHEEL' {
            & $script:Python -m pip install --disable-pip-version-check $script:Wheel
            if (-not (Test-Path $script:Lbe)) { throw 'INSTALLED_LBE_ENTRYPOINT_MISSING' }
        }

        Invoke-Stage 'INSTALLED_ORIGIN_PROOF' {
            $ProbeDir = Join-Path $RunRoot 'origin-probe'
            New-Item -ItemType Directory -Force $ProbeDir | Out-Null
            Push-Location $ProbeDir
            try {
                & $script:Python -c "from pathlib import Path; import agent,lbe_guard_inspector; a=Path(agent.__file__).resolve(); l=Path(lbe_guard_inspector.__file__).resolve(); print('AGENT='+str(a)); print('LBE='+str(l)); assert 'site-packages' in str(a).lower(); assert 'site-packages' in str(l).lower()"
            }
            finally {
                Pop-Location
            }
        }

        Invoke-Stage 'INSTALLED_CLINE_DEPENDENCY_RESOLUTION' {
            $WorkerRoot = Join-Path $script:Venv 'Lib\site-packages\lbe_guard_inspector\runtime\cline_worker'
            if (-not (Test-Path (Join-Path $WorkerRoot 'worker.mjs'))) { throw 'INSTALLED_WORKER_MISSING' }
            Push-Location $WorkerRoot
            try {
                node --input-type=module -e "import('@cline/agents').then(m=>{console.log('CLINE_AGENTS_RESOLUTION=PASS');console.log('AgentRuntime='+typeof m.AgentRuntime);console.log('createAgentRuntime='+typeof m.createAgentRuntime)}).catch(e=>{console.error(e);process.exit(1)})"
            }
            finally {
                Pop-Location
            }
        }

        Invoke-Stage 'INSTALLED_CLI_SMOKE' {
            & $script:Lbe --help | Select-Object -First 40
        }

        Invoke-Stage 'FULL_OBSERVABLE_13' {
            $Scratch = Join-Path $RunRoot 'observable13-scratch'
            New-Item -ItemType Directory -Force $Scratch | Out-Null
            & $script:Python (Join-Path $Root 'scripts\r7_observable13_installed_probe.py') --repo-root $Root --venv $script:Venv --scratch-dir $Scratch
        }

        Invoke-Stage 'FINAL_SOURCE_AUTHORITY_CHECK' {
            $Head = (git rev-parse HEAD).Trim()
            $Origin = (git rev-parse origin/main).Trim()
            Write-Output "HEAD=$Head"
            Write-Output "ORIGIN_MAIN=$Origin"
            if ($Head -ne $Origin) { throw 'HEAD_CHANGED_DURING_VALIDATION' }
            Write-Output '=== GIT STATUS ==='
            git status --short
        }

        Write-Output ''
        Write-Output '================================================================'
        Write-Output 'PIPELINE_RESULT=PASS'
        Write-Output "STAGES_PASSED=$Stage"
        Write-Output "LOG=$Log"
        Write-Output '================================================================'
    }
    finally {
        Pop-Location
    }

    Stop-Transcript | Out-Null
    exit 0
}
catch {
    try { Stop-Transcript | Out-Null } catch {}
    Write-Output ''
    Write-Output 'PIPELINE_RESULT=FAIL'
    Write-Output "STOPPED_AT_STAGE=$Stage"
    Write-Output "LOG=$Log"
    if (Test-Path $Log) {
        Write-Output '=== LOG TAIL ==='
        Get-Content $Log -Tail 180
    }
    exit 1
}
