param([string]$Targets='PvZPvPNative typed72_battle_audit cpp_tests')
# Windows Release build of the production app (typed72 kernel stage v43 + generated composition)
# into a new directory, serially (compiler heap limits). Records the configuration and source hashes.
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$cmake='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$out="$root\build\app-typed72-v2"
$stage="$root/build/typed72-integrated-v44/source"
$env:_CL_='/MP1 /FS'
& $cmake -S $root -B $out -G 'Visual Studio 17 2022' -A x64 "-DPVZ_TYPED72_STAGE=$stage" -DPVZ_BUILD_DEVELOPER_CANDIDATE=OFF -DPVZ_BUILD_TYPED72_STAGES=OFF *> "$out-configure.log"
"configure=$LASTEXITCODE"
foreach($t in $Targets.Split(' ')){
    & $cmake --build $out --config Release --target $t --parallel 1 *> "$out-build-$t.log"
    "build $t=$LASTEXITCODE"
    if($LASTEXITCODE -ne 0){Select-String -Path "$out-build-$t.log" -Pattern ' error ' | Select-Object -First 8 | ForEach-Object {$_.Line.Substring(0,[Math]::Min(240,$_.Line.Length))};break}
}
