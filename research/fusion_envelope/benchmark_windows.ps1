param(
    [int]$Repetitions = 5,
    [string]$Reference = 'research/joint_budget/results/envelope_attention96_relaxed_events_1.json',
    [string]$OutputDirectory = 'research/joint_budget/results/formal_attention128',
    [switch]$PushEachTrial
)
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$runtimeWrapper = Join-Path $repoRoot 'research/runtime/run_windows.ps1'
$methods = @('events','shape','lp','correlated')
if ($Repetitions -lt 5) { throw 'Formal timing requires at least five repetitions.' }
$expectedBranch = 'codex/chat-supervised-joint-synthesis'
$branch = (& git -C $repoRoot branch --show-current).Trim()
if ($branch -ne $expectedBranch) { throw "Unexpected branch: $branch" }
$codeCommit = (& git -C $repoRoot rev-parse HEAD).Trim()
$outAbs = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
if (-not $outAbs.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar)) {
    throw 'Output directory must remain within this repository.'
}
New-Item -ItemType Directory -Path $outAbs -Force | Out-Null
$settings = @('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')
$previous = @{}
foreach ($key in $settings) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key,'Process')
    [Environment]::SetEnvironmentVariable($key,'1','Process')
}
try {
    for ($round = 1; $round -le $Repetitions; $round++) {
        for ($position = 0; $position -lt $methods.Count; $position++) {
            # Rotate order to reduce systematic OS-cache/thermal order effects.
            $method = $methods[($position + $round - 1) % $methods.Count]
            $stem = "${method}_r${round}"
            $reportRel = "$OutputDirectory/$stem.json"
            $checkRel = "$OutputDirectory/${stem}_check.json"
            $reportAbs = Join-Path $repoRoot $reportRel
            if (Test-Path -LiteralPath $reportAbs) {
                $existing = Get-Content -LiteralPath $reportAbs -Raw | ConvertFrom-Json
                if ($existing.status -eq 'complete' -and (Test-Path -LiteralPath (Join-Path $repoRoot $checkRel))) {
                    Write-Output "Skipping already completed $stem"
                    continue
                }
                throw "Refusing to overwrite an incomplete trial: $reportRel"
            }
            if ((& git -C $repoRoot branch --show-current).Trim() -ne $expectedBranch) {
                throw 'Branch changed during benchmark.'
            }
            Write-Output "START round=$round method=$method code=$codeCommit"
            $trialArgs = @('-m','research.fusion_envelope.search','--method',$method,
                '--policy','relaxed','--workload','attention','--domain','factors96',
                '--reference',$Reference,'--output',$reportRel)
            $wall = [Diagnostics.Stopwatch]::StartNew()
            & $runtimeWrapper -PythonArguments $trialArgs *> (Join-Path $outAbs "$stem.log")
            if ($LASTEXITCODE -ne 0) { throw "Search failed: $stem" }
            $wall.Stop()
            $proofArgs = @('-m','research.fusion_envelope.check_certificate','--report',$reportRel,
                          '--reference',$Reference,'--output',$checkRel)
            & $runtimeWrapper -PythonArguments $proofArgs *> (Join-Path $outAbs "${stem}_check.log")
            if ($LASTEXITCODE -ne 0) { throw "Independent certificate check failed: $stem" }
            $finished = Get-Content -LiteralPath $reportAbs -Raw | ConvertFrom-Json
            if ($finished.status -ne 'complete') { throw "Non-complete report: $stem" }
            Write-Output "PASS round=$round method=$method search_s=$($finished.search_s) native_solves=$($finished.native_solves) pruned=$($finished.pruned_hardware) process_wall_s=$($wall.Elapsed.TotalSeconds)"
            if ($PushEachTrial) {
                & git -C $repoRoot add -- $reportRel $checkRel
                if ($LASTEXITCODE -ne 0) { throw 'Could not stage verified trial.' }
                & git -C $repoRoot commit --only -m "Record verified relaxed Attention $method trial $round" -- $reportRel $checkRel
                if ($LASTEXITCODE -ne 0) { throw 'Could not commit verified trial.' }
                & git -C $repoRoot push
                if ($LASTEXITCODE -ne 0) { throw 'Could not push verified trial.' }
            }
        }
    }
} finally {
    foreach ($key in $settings) {
        [Environment]::SetEnvironmentVariable($key,$previous[$key],'Process')
    }
}
