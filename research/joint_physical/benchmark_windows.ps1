param(
    [int]$Repetitions = 5,
    [ValidateSet('attention','attention256','attention512')][string]$Workload = 'attention',
    [string]$OutputDirectory = 'research/joint_budget/results/formal_demand128',
    [switch]$PushEachTrial
)
$ErrorActionPreference = 'Stop'
if ($Repetitions -lt 5) { throw 'At least five fresh-process repetitions required.' }
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$runtime = Join-Path $root 'research/runtime/run_windows.ps1'
$expectedBranch = 'codex/chat-supervised-joint-synthesis'
$code = (& git -C $root rev-parse HEAD).Trim()
$out = [IO.Path]::GetFullPath((Join-Path $root $OutputDirectory))
if (-not $out.StartsWith($root + [IO.Path]::DirectorySeparatorChar)) { throw 'Output directory outside repository.' }
New-Item -ItemType Directory -Path $out -Force | Out-Null
$reference = "$OutputDirectory/events_r1.json"
$settings = @{ OMP_NUM_THREADS='1'; OPENBLAS_NUM_THREADS='1'; MKL_NUM_THREADS='1'; NUMEXPR_NUM_THREADS='1'; PYTHONHASHSEED='0' }
$previous = @{}
foreach ($key in $settings.Keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key,'Process')
    [Environment]::SetEnvironmentVariable($key,$settings[$key],'Process')
}
try {
    for ($round = 1; $round -le $Repetitions; $round++) {
        $methods = if ($round % 2) { @('events','demand') } else { @('demand','events') }
        foreach ($method in $methods) {
            if ((& git -C $root branch --show-current).Trim() -ne $expectedBranch) { throw 'Unexpected branch.' }
            $stem = "${method}_r${round}"
            $result = "$OutputDirectory/$stem.json"
            $proof = "$OutputDirectory/${stem}_check.json"
            if (Test-Path -LiteralPath (Join-Path $root $result)) {
                $existing = Get-Content -LiteralPath (Join-Path $root $result) -Raw | ConvertFrom-Json
                if ($existing.status -eq 'complete' -and (Test-Path -LiteralPath (Join-Path $root $proof))) {
                    Write-Output "SKIP verified $stem"
                    continue
                }
                throw "Refusing to overwrite incomplete or unverified trial: $result"
            }
            Write-Output "START $Workload round=$round method=$method code=$code"
            if ($method -eq 'events') {
                $argsForTrial = @('-m','research.fusion_envelope.search','--method','events','--policy','relaxed',
                    '--workload',$Workload,'--domain','factors96','--output',$result)
            } else {
                $argsForTrial = @('-m','research.joint_physical.run','--method','demand','--rounds','1','--seed-wave',
                    '--workload',$Workload,'--domain','factors96','--reference',$reference,'--output',$result)
            }
            & $runtime -PythonArguments $argsForTrial *> (Join-Path $out "$stem.log")
            if ($LASTEXITCODE -ne 0) { throw "Search failed: $stem" }
            $argsForReplay = @('-m','research.joint_physical.replay','--report',$result,'--output',$proof)
            if ($result -ne $reference) { $argsForReplay += @('--reference',$reference) }
            & $runtime -PythonArguments $argsForReplay *> (Join-Path $out "${stem}_check.log")
            if ($LASTEXITCODE -ne 0) { throw "Independent physical replay failed: $stem" }
            $report = Get-Content -LiteralPath (Join-Path $root $result) -Raw | ConvertFrom-Json
            Write-Output "PASS $Workload round=$round method=$method search_s=$($report.search_s)"
            if ($PushEachTrial) {
                & git -C $root add -- $result $proof
                if ($LASTEXITCODE -ne 0) { throw 'Could not stage verified trial.' }
                & git -C $root commit --only -m "Record $Workload $method verified joint-search trial $round" -- $result $proof
                if ($LASTEXITCODE -ne 0) { throw 'Could not commit verified trial.' }
                & git -C $root push
                if ($LASTEXITCODE -ne 0) { throw 'Could not push verified trial.' }
            }
        }
    }
} finally {
    foreach ($key in $settings.Keys) { [Environment]::SetEnvironmentVariable($key,$previous[$key],'Process') }
}
