param([string]$Version)
# Fresh integrated stage with symbols for match iteration; older stages stay intact.
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$python='C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\tools\python38-embed\python.exe'
$cmake='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
Set-Location -LiteralPath $root
$stage="build/typed72-integrated-$Version"
& $python -I tools/typed72/integrate_stage.py --stage $stage
Copy-Item build/typed72-integrated-v5/CMakeLists.txt "$stage/CMakeLists.txt"
$env:_CL_='/MP1 /FS'
& $cmake -S $stage -B "$stage/build-zi" -G 'Visual Studio 17 2022' -A x64 -DPVZ_ZI=ON *> "$stage/configure-zi.log"
& $cmake --build "$stage/build-zi" --config Release --target pvztyped72 --parallel 1 *> "$stage/lib-build-zi.log"; "lib=$LASTEXITCODE"
if($LASTEXITCODE -ne 0){Select-String -Path "$stage/lib-build-zi.log" -Pattern ' error ' | Select-Object -First 12 | ForEach-Object {$_.Line.Substring(0,[Math]::Min(220,$_.Line.Length))}}
$m='build/typed72-match-v1/CMakeLists.txt';$c=[IO.File]::ReadAllText("$root/$m");$c=[regex]::Replace($c,'typed72-integrated-v\d+',"typed72-integrated-$Version");[IO.File]::WriteAllText("$root/$m",$c,[Text.UTF8Encoding]::new($false))
