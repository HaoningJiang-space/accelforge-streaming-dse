param([string[]]$Cases = @('semantics', '2mm_grid', '3mm_grid', '2mm_threshold', '2mm_edge'))
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runner = Join-Path $repoRoot 'research/runtime/run_windows.ps1'
$definitions = @{
    semantics = @('--params','2,4,8','--shapes','4x8','--capacities','96','--modes','graph,zero_loops,materialized')
    '2mm_grid' = @('--params','2,8,16','--shapes','2x8,4x4,8x2','--capacities','64,96,128,192,256','--modes','graph,materialized')
    '3mm_grid' = @('--params','3,8,16','--shapes','2x8,4x4,8x2','--capacities','64,96,128,192,256','--modes','graph,materialized')
    '2mm_threshold' = @('--params','2,8,16','--shapes','2x8,4x4,8x2','--capacities','176,184,191,192,193,200,208','--modes','graph,materialized')
    '2mm_edge' = @('--params','2,8,16','--shapes','2x8,4x4','--capacities','175,176,207,208','--modes','graph,materialized')
}
Push-Location $repoRoot
try {
    foreach ($caseName in $Cases) {
        if (-not $definitions.ContainsKey($caseName)) { throw "Unknown case: $caseName" }
        $outputPath = "research/motivation/results/$caseName.json"
        $logPath = "research/motivation/results/$caseName.log"
        New-Item -ItemType Directory -Force research/motivation/results | Out-Null
        Write-Output "Running $caseName (one FFM worker)"
        $arguments = @('-m','research.motivation.native_study') + $definitions[$caseName] + @('--output',$outputPath)
        & $runner -PythonArguments $arguments *> $logPath
        if ($LASTEXITCODE -ne 0) { throw "$caseName failed; see $logPath" }
        Write-Output "Completed $caseName"
    }
} finally {
    Pop-Location
}
