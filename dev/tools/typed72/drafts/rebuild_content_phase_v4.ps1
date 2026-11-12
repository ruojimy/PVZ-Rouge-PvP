$ErrorActionPreference='Stop'
$workspace='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$stage=Join-Path $workspace 'build/typed72-content-controller-v4'
$typed=Join-Path $stage 'source/src/sim/typed'
$draft=Join-Path $workspace 'tools/typed72/drafts'
$cmake='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
foreach($name in @('content_damage.h','content_damage.cpp','chili_effects.h','chili_effects.cpp','entity_phase.h','entity_phase.cpp','native_content_phase.h','native_content_phase.cpp')){
    Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $typed $name)
}
foreach($name in @('content_controllers_probe.cpp','content_phase_probe.cpp')){
    Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $stage $name)
}
$configPath=Join-Path $typed 'CMakeLists.txt'
$config=[IO.File]::ReadAllText($configPath)
if(-not $config.Contains('add_executable(content_phase72_probe')){
    $config+="`nadd_executable(content_phase72_probe `"$($stage.Replace('\','/'))/content_phase_probe.cpp`")`ntarget_link_libraries(content_phase72_probe PRIVATE pvztyped72)`ntarget_include_directories(content_phase72_probe PRIVATE `"`${PVZ_TYPED_ROOT}/third_party`" `"`${PVZ_TYPED_ROOT}/tools/typed72`")`n"
}
[IO.File]::WriteAllText($configPath,$config,[Text.UTF8Encoding]::new($false))
$manifest=Join-Path $stage 'controller-build-inputs.json'
if(-not (Test-Path -LiteralPath (Join-Path $stage 'controller-build-inputs-r1.json'))){Copy-Item -LiteralPath $manifest -Destination (Join-Path $stage 'controller-build-inputs-r1.json')}
$pinned=[ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $stage 'source') -Recurse -File | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
Get-ChildItem -LiteralPath $stage -File -Filter '*.cpp' | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$pinned | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifest -Encoding UTF8
& $cmake -S $typed -B (Join-Path $stage 'build') -G 'Visual Studio 17 2022' -A x64 *> (Join-Path $stage 'phase-configure.log')
if($LASTEXITCODE -ne 0){throw "CMake configure failed: $LASTEXITCODE"}
& $cmake --build (Join-Path $stage 'build') --config Release --target content_controllers72_probe content_phase72_probe --parallel 1 *> (Join-Path $stage 'phase-build.log')
exit $LASTEXITCODE
