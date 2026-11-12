$stage=$PSScriptRoot
$cmake='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$env:_CL_='/MP1 /FS'
& $cmake -S $stage -B "$stage/build" -G 'Visual Studio 17 2022' -A x64 *> "$stage/configure.log"
& $cmake --build "$stage/build" --config Release --parallel 1 *> "$stage/match-build.log"; "build=$LASTEXITCODE"
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\xiech\Downloads\PVZ-Rouge-v1.4.8\next-pvp71\modkit\tools\python38-embed\python.exe' -I "$stage/errs2.py" "$stage/match-build.log" 40
