param()

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    Write-Error "LBE WORKSPACE LOCK: BLOCKED: $Message"
    exit 1
}

$root = (git rev-parse --show-toplevel).Trim()
if (-not $root) { Fail 'not inside a Git worktree' }
Set-Location $root

$branch = (git symbolic-ref --quiet --short HEAD 2>$null).Trim()
if ($branch -ne 'main') { Fail "current branch must be main (got: $branch)" }

$worktreeLines = git worktree list --porcelain
$primaryLine = $worktreeLines | Where-Object { $_ -like 'worktree *' } | Select-Object -First 1
if (-not $primaryLine) { Fail 'cannot resolve primary worktree' }
$primary = $primaryLine.Substring('worktree '.Length)

$rootResolved = (Resolve-Path $root).Path.TrimEnd('\','/')
$primaryResolved = (Resolve-Path $primary).Path.TrimEnd('\','/')
if ($rootResolved -ne $primaryResolved) {
    Fail "workspace lock can only be enabled from the primary worktree: $primaryResolved"
}

$origin = (git remote get-url origin).Trim()
if ($origin -notmatch 'Letterblack0306[/\\:]LBE_Presistent_Agent_wall(?:\.git)?$') {
    Fail "origin is not the canonical repository: $origin"
}

python scripts/check-implementation-gate.py
if ($LASTEXITCODE -ne 0) { Fail 'implementation gate validation failed' }

$hooksPath = Join-Path $primaryResolved '.githooks'
if (-not (Test-Path -LiteralPath $hooksPath -PathType Container)) {
    Fail "canonical hook directory is missing: $hooksPath"
}

git config --local core.hooksPath $hooksPath
git config --local lbe.workspaceLock enabled

$hookPath = (git config --local --get core.hooksPath).Trim()
if ($hookPath -ne $hooksPath) { Fail 'failed to configure canonical core.hooksPath' }

Write-Output 'LBE WORKSPACE LOCK: ENABLED'
Write-Output "Repository: Letterblack0306/LBE_Presistent_Agent_wall"
Write-Output "Primary worktree: $primaryResolved"
Write-Output 'Branch: main'
Write-Output 'Push target: origin/main only'
Write-Output 'Pre-commit progression gate: enabled'
