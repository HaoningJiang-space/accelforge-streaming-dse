param(
    [string]$EnvironmentPath = "$env:USERPROFILE/.codex/envs/accelforge",
    [string]$Micromamba = "$env:USERPROFILE/.codex/tools/micromamba/Library/bin/micromamba.exe",
    [string[]]$PythonArguments = @('-m', 'pytest', '-q', 'research/joint_synthesis/tests')
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $EnvironmentPath 'python.exe'))) {
    throw "Research Python environment is missing: $EnvironmentPath. See research/runtime/README.md."
}
if (-not (Test-Path -LiteralPath $Micromamba)) {
    throw "micromamba is missing: $Micromamba"
}
$oldConfig = $env:ACCELFORGE_CONFIG_PATH
$oldEncoding = $env:PYTHONUTF8
Push-Location -LiteralPath $repoRoot
try {
    $env:ACCELFORGE_CONFIG_PATH = Join-Path $PSScriptRoot 'windows_config.yaml'
    $env:PYTHONUTF8 = '1'
    & $Micromamba run -p $EnvironmentPath python @PythonArguments
    $runExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:ACCELFORGE_CONFIG_PATH = $oldConfig
    $env:PYTHONUTF8 = $oldEncoding
}
exit $runExit
