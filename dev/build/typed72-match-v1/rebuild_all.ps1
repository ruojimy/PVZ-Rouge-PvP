# Serial rebuild after a driver/app change: composition -> match driver -> production app,
# audit tool and cpp_tests (incremental, build/app-typed72-v2). Kernel stage stays v43.
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
Set-Location -LiteralPath $root
& 'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\tools\python38-embed\python.exe' -I tools\typed72\make_app_composition.py
$m=& "$root\build\typed72-match-v1\build_match.ps1" 2>&1; "match: " + ($m -join ' ')
if(-not ($m -contains 'build=0')){ Select-String -Path "$root\build\typed72-match-v1\match-build.log" -Pattern ' error ' | Select-Object -First 8 | ForEach-Object {$_.Line.Substring(0,[Math]::Min(240,$_.Line.Length))}; exit 1 }
$cmake='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$env:_CL_='/MP1 /FS'
foreach($t in 'PvZPvPNative','typed72_battle_audit','cpp_tests'){
    & $cmake --build "$root\build\app-typed72-v2" --config Release --target $t --parallel 1 *> "$root\build\app-typed72-v2-rebuild-$t.log"
    "app $t=$LASTEXITCODE"
    if($LASTEXITCODE -ne 0){Select-String -Path "$root\build\app-typed72-v2-rebuild-$t.log" -Pattern ' error ' | Select-Object -First 8 | ForEach-Object {$_.Line.Substring(0,[Math]::Min(240,$_.Line.Length))};exit 1}
}
"rebuild done"
