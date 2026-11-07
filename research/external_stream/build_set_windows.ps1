param([string]$Uv = "$env:USERPROFILE/.codex/tools/uv/uv.exe", [switch]$Include3mm, [switch]$DagDriver)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$checkout = Join-Path $root 'libraries/set-isca2023'
$revision = 'a7bd73912f58d9fea10fadab693eebd4e6e3054d'
if (-not (Test-Path -LiteralPath (Join-Path $checkout '.git'))) {
    & git clone https://github.com/SET-Scheduling-Project/SET-ISCA2023.git $checkout
    if ($LASTEXITCODE) { throw 'SET clone failed.' }
    & git -C $checkout checkout --detach $revision
    if ($LASTEXITCODE) { throw 'SET checkout failed.' }
}
if ((& git -C $checkout rev-parse HEAD).Trim() -ne $revision -or
    (& git -C $checkout status --porcelain --untracked-files=no)) { throw 'SET revision differs.' }
$compilerEnv = Join-Path $checkout '.compiler'
$compiler = Join-Path $compilerEnv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    & $Uv venv $compilerEnv --python (Join-Path $root '.venv/Scripts/python.exe')
    if ($LASTEXITCODE) { throw 'Could not make compiler environment.' }
}
& $Uv pip install --python $compiler 'ziglang==0.15.2'
if ($LASTEXITCODE) { throw 'Could not install the isolated Zig toolchain.' }
Push-Location -LiteralPath $checkout
try {
    New-Item -ItemType Directory -Force build | Out-Null
    # The only porting change replaces two libstdc++ extensions in a build copy.
    $copy = Get-Content -LiteralPath src/bitset.cpp -Raw
    $first = 'return static_cast<Bitset::bitlen_t>(std_bs::_Find_first());'
    $next = 'return static_cast<Bitset::bitlen_t>(std_bs::_Find_next(bit));'
    if (-not ($copy.Contains($first) -and $copy.Contains($next))) { throw 'Unexpected bitset implementation.' }
    $copy = $copy.Replace($first, 'for (bitlen_t i = 0; i < size(); ++i) if (contains(i)) return i; return size();')
    $copy = $copy.Replace($next, 'for (bitlen_t i = bit + 1; i < size(); ++i) if (contains(i)) return i; return size();')
    Set-Content -LiteralPath build/bitset_portable.cpp -Value $copy -Encoding utf8
    $sources = @(Get-ChildItem -LiteralPath src -Recurse -Filter '*.cpp' | Where-Object Name -ne 'bitset.cpp' |
        ForEach-Object { Resolve-Path -Relative $_.FullName })
    $sources += 'build/bitset_portable.cpp'
    if ($DagDriver -and $Include3mm) { throw 'Choose one SET entry point.' }
    if ($Include3mm) {
        $main = Get-Content -LiteralPath src/main.cpp -Raw
        $insertion = 'static const std::unordered_map<std::string, const Network*> All_Networks = {'
        if (-not $main.Contains($insertion)) { throw 'Unexpected SET workload registry.' }
        $adapter = @'
static const Network native_3mm = [] {
    Network n;
    n.add(NLAYER("Matmul0", Conv, C=256, K=256, H=256, W=1, R=1, S=1), {}, 8,
          {InputData("T0", fmap_shape(256, 256, 1))});
    n.add(NLAYER("Matmul1", Conv, C=256, K=256, H=256, W=1, R=1, S=1));
    n.add(NLAYER("Matmul2", Conv, C=256, K=256, H=256, W=1, R=1, S=1));
    return n;
}();

'@
        $main = $main.Replace($insertion, ($adapter + $insertion + [Environment]::NewLine + '  {"native_3mm", &native_3mm},'))
        Set-Content -LiteralPath build/main_with_3mm.cpp -Value $main -Encoding utf8
        $sources = @($sources | Where-Object { (Split-Path $_ -Leaf) -ne 'main.cpp' })
        $sources += 'build/main_with_3mm.cpp'
    }
    $binary = 'build/stschedule.exe'
    if ($DagDriver) {
        $sources = @($sources | Where-Object { (Split-Path $_ -Leaf) -ne 'main.cpp' })
        $sources += (Join-Path $PSScriptRoot 'set_dag_driver.cpp')
        $binary = 'build/dag_driver.exe'
    }
    & $compiler -m ziglang c++ -std=c++17 -O2 -Iinclude -o $binary @sources
    if ($LASTEXITCODE) { throw 'SET compilation failed.' }
} finally { Pop-Location }
