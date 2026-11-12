$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$sourceStage = Join-Path $workspace 'build\typed72-native-clock-stage'
$stage = Join-Path $workspace 'build\typed72-content-controller-stage'
$draft = Join-Path $workspace 'tools\typed72\drafts'
$cmake = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
if (Test-Path -LiteralPath $stage) { throw 'New stage already exists; inspect before reuse.' }
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceStage 'source') -Destination $stage -Recurse
foreach ($name in @('native_tick_probe.cpp','native_status_probe.cpp','native_clock_probe.cpp','wind_probe.cpp')) {
    Copy-Item -LiteralPath (Join-Path $sourceStage $name) -Destination (Join-Path $stage $name)
}
$typed = Join-Path $stage 'source\src\sim\typed'
foreach ($name in @('content_zombies.h','content_zombies.cpp','content_zombie_state.h','cart_lifecycle.h','cart_lifecycle.cpp','native_status_state.h')) {
    Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $typed $name)
}
Copy-Item -LiteralPath (Join-Path $draft 'content_zombies_probe.cpp') -Destination (Join-Path $stage 'content_zombies_probe.cpp')
$targetPath = Join-Path $typed 'targets.h'
$target = [IO.File]::ReadAllText($targetPath)
$target = $target.Replace('#include "sim/typed/content_zombie64_state.h"', "#include `"sim/typed/content_zombie64_state.h`"`n#include `"sim/typed/content_zombie_state.h`"")
$target = $target.Replace('ContentZombie64State content64;', "ContentZombie64State content64;`n    ContentZombieState content;")
if (-not $target.Contains('ContentZombieState content;')) { throw 'Content state field insertion failed' }
[IO.File]::WriteAllText($targetPath,$target,[Text.UTF8Encoding]::new($false))
$cmakePath = Join-Path $typed 'CMakeLists.txt'
$config = [IO.File]::ReadAllText($cmakePath).Replace($sourceStage.Replace('\','/'),$stage.Replace('\','/')).Replace('/MP1','/MP1 /FS')
$config += @'

target_sources(pvztyped72 PRIVATE content_zombies.cpp cart_lifecycle.cpp)
add_executable(content_zombies72_probe "CONTENT_STAGE/content_zombies_probe.cpp")
target_link_libraries(content_zombies72_probe PRIVATE pvztyped72)
target_include_directories(content_zombies72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
'@.Replace('CONTENT_STAGE',$stage.Replace('\','/'))
[IO.File]::WriteAllText($cmakePath,$config,[Text.UTF8Encoding]::new($false))
$pinned = [ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $stage 'source') -Recurse -File | ForEach-Object { $pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
Get-ChildItem -LiteralPath $stage -File -Filter '*.cpp' | ForEach-Object { $pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
$pinned | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'build-inputs.json') -Encoding UTF8
& $cmake -S $typed -B (Join-Path $stage 'build') -G 'Visual Studio 17 2022' -A x64 *> (Join-Path $stage 'configure.log')
if ($LASTEXITCODE -ne 0) { throw "CMake configuration failed: $LASTEXITCODE" }
& $cmake --build (Join-Path $stage 'build') --config Release --target content_zombies72_probe --parallel 1 *> (Join-Path $stage 'release-build.log')
exit $LASTEXITCODE
