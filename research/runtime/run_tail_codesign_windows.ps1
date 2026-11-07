param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateRange(1,96)][int]$Queries=32,
    [switch]$SkipExactAnchor
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtime = Join-Path $root 'research/runtime/run_windows.ps1'
Push-Location -LiteralPath $root
try {
    New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
    $seeds = Join-Path $OutputDirectory 'joint_seeds.json'
    $tail = Join-Path $OutputDirectory 'tail_designs.json'
    if ((Test-Path -LiteralPath $seeds) -or (Test-Path -LiteralPath $tail)) {
        throw 'Use a fresh output directory.'
    }
    if ($SkipExactAnchor) {
        & $runtime -PythonArguments @('-m','research.joint_physical.run','--method','demand',
            '--workload','3mm','--domain','factors96','--proposal-policy','independent','--output',$seeds)
    } else {
        & $runtime -PythonArguments @('-m','research.runtime.refine_joint','--workload','3mm','--output',$seeds)
    }
    if ($LASTEXITCODE) { throw 'Native joint seed search failed.' }
    & $runtime -PythonArguments @('-m','research.runtime.tail_online','--seeds',$seeds,
        '--queries',"$Queries",'--output',$tail)
    if ($LASTEXITCODE) { throw 'Physical tail search failed.' }
} finally { Pop-Location }
