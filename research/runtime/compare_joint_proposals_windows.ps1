param(
    [ValidateSet('3mm','attention','attention256','attention512')][string]$Workload,
    [ValidateSet('original12','factors96')][string]$Domain = 'factors96',
    [Parameter(Mandatory=$true)][string]$Reference,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('feedback','independent','independent-wide','prefix')][string[]]$Policies,
    [switch]$PushEachTrial
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtime = Join-Path $root 'research/runtime/run_windows.ps1'
$branch = 'codex/chat-supervised-joint-synthesis'
$settings = @{ OMP_NUM_THREADS='1'; OPENBLAS_NUM_THREADS='1'; MKL_NUM_THREADS='1'; NUMEXPR_NUM_THREADS='1'; PYTHONHASHSEED='0' }
$previous = @{}
foreach ($key in $settings.Keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key,'Process')
    [Environment]::SetEnvironmentVariable($key,$settings[$key],'Process')
}
Push-Location -LiteralPath $root
try {
    New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
    foreach ($policy in $Policies) {
        $result = "$OutputDirectory/$policy.json"
        $check = "$OutputDirectory/${policy}_check.json"
        if (Test-Path -LiteralPath $result) { throw "Refusing to overwrite $result" }
        & $runtime -PythonArguments @('-m','research.joint_physical.run','--method','demand','--workload',$Workload,
            '--domain',$Domain,'--proposal-policy',$policy,'--allow-quality-gap','--reference',$Reference,
            '--output',$result) *> "$OutputDirectory/$policy.log"
        if ($LASTEXITCODE) { throw "Proposal search failed: $policy" }
        & $runtime -PythonArguments @('-m','research.joint_physical.replay','--report',$result,'--reference',$Reference,
            '--allow-quality-gap','--output',$check) *> "$OutputDirectory/${policy}_check.log"
        if ($LASTEXITCODE) { throw "Independent physical replay failed: $policy" }
        Get-Content -LiteralPath $check
        if ($PushEachTrial) {
            if ((& git branch --show-current).Trim() -ne $branch) { throw 'Unexpected branch.' }
            & git add -- $result $check
            if ($LASTEXITCODE) { throw 'Could not stage verified trial.' }
            & git commit --only -m "Record verified $Workload $policy proposal diagnostic" -- $result $check
            if ($LASTEXITCODE) { throw 'Could not commit verified trial.' }
            & git push
            if ($LASTEXITCODE) { throw 'Could not push verified trial.' }
        }
    }
} finally {
    Pop-Location
    foreach ($key in $settings.Keys) {
        [Environment]::SetEnvironmentVariable($key,$previous[$key],'Process')
    }
}
