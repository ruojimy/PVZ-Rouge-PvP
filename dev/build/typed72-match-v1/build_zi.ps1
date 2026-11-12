$stage='C:\Users\xiech\Downloads\PVZ_rougePvP_native\build\typed72-integrated-v5'
$cmake='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$env:_CL_='/MP1 /FS'
& $cmake -S $stage -B "$stage/build-zi" -G 'Visual Studio 17 2022' -A x64 -DPVZ_ZI=ON *> "$stage/configure-zi.log"; "cfg=$LASTEXITCODE"
& $cmake --build "$stage/build-zi" --config Release --target pvztyped72 --parallel 1 *> "$stage/lib-build-zi.log"; "lib=$LASTEXITCODE"
