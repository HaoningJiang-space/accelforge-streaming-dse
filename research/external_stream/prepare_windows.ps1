param([string]$Uv = "$env:USERPROFILE/.codex/tools/uv/uv.exe")
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$stream = Join-Path $root 'libraries/stream'
$zigzag = Join-Path $root 'libraries/zigzag'
$envPath = Join-Path $stream '.venv'
$python = Join-Path $envPath 'Scripts/python.exe'
$base = Join-Path $root '.venv/Scripts/python.exe'

function Checkout-Pinned($Path, $Url, $Revision) {
    if (-not (Test-Path -LiteralPath (Join-Path $Path '.git'))) {
        & git clone $Url $Path
        if ($LASTEXITCODE) { throw "Clone failed: $Url" }
        & git -C $Path checkout --detach $Revision
        if ($LASTEXITCODE) { throw "Checkout failed: $Revision" }
    }
    if ((& git -C $Path rev-parse HEAD).Trim() -ne $Revision) { throw "Unexpected revision in $Path" }
    if (& git -C $Path status --porcelain --untracked-files=no) { throw "Modified vendor sources in $Path" }
}

Checkout-Pinned $stream 'https://github.com/KULeuven-MICAS/stream.git' '407d373f942101895b72b3e6d2c75dbe714633a6'
Checkout-Pinned $zigzag 'https://github.com/KULeuven-MICAS/zigzag.git' 'd0b2add2dd5c3d827291c8ebe13a5016b08dc65c'
if (-not (Test-Path -LiteralPath $python)) {
    & $Uv venv $envPath --python $base
    if ($LASTEXITCODE) { throw 'Could not create the isolated STREAM environment.' }
}
& $Uv pip install --python $python -e $stream $zigzag pytest pytest-timeout
if ($LASTEXITCODE) { throw 'Could not install STREAM and ZigZag.' }
& $Uv pip check --python $python
exit $LASTEXITCODE
