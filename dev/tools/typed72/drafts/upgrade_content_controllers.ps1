$ErrorActionPreference='Stop'
$workspace='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$previousStage=Join-Path $workspace 'build\typed72-content-controller-stage'
$stage=Join-Path $workspace 'build\typed72-content-controller-v2'
$typed=Join-Path $stage 'source\src\sim\typed'
$draft=Join-Path $workspace 'tools\typed72\drafts'
$cmake='C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
if(Test-Path -LiteralPath $stage){throw 'New controller v2 stage already exists; inspect before reuse.'}
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $previousStage 'source') -Destination $stage -Recurse
foreach($name in @('native_clock_probe.cpp','wind_probe.cpp')) {
    Copy-Item -LiteralPath (Join-Path $previousStage $name) -Destination (Join-Path $stage $name)
}
$files=@('native_tick.h','native_tick.cpp','native_status.h','native_status.cpp','native_status_state.h',
    'hero.h','hero.cpp','combat_events.h','sourced_context.cpp',
    'content_zombies.h','content_zombies.cpp','content_zombie_state.h','cart_lifecycle.h','cart_lifecycle.cpp',
    'content_zombie56_state.h','content_zombies56.h','content_zombies56.cpp',
    'content_zombie70_state.h','content_zombies70.h','content_zombies70.cpp',
    'september_zombies.h','september_zombies.cpp','native_barrels.h','native_barrels.cpp',
    'content_zombie_bindings.h','content_zombie_bindings.cpp')
foreach($name in $files){Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $typed $name)}
foreach($name in @('content_zombies_probe.cpp','content_controllers_probe.cpp','native_status_probe.cpp','native_tick_probe.cpp')) {
    Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $stage $name)
}
$targetPath=Join-Path $typed 'targets.h'
$targets=[IO.File]::ReadAllText($targetPath)
if(-not $targets.Contains('ContentZombie56State content56;')) {
    $targets=$targets.Replace('#include "sim/typed/content_zombie_state.h"',"#include `"sim/typed/content_zombie_state.h`"`n#include `"sim/typed/content_zombie56_state.h`"`n#include `"sim/typed/content_zombie70_state.h`"")
    $targets=$targets.Replace('ContentZombieState content;',"ContentZombieState content;`n    ContentZombie56State content56;`n    ContentZombie70State content70;")
}
[IO.File]::WriteAllText($targetPath,$targets,[Text.UTF8Encoding]::new($false))
$configPath=Join-Path $typed 'CMakeLists.txt'
$config=[IO.File]::ReadAllText($configPath).Replace($previousStage.Replace('\','/'),$stage.Replace('\','/'))
if(-not $config.Contains('PRIVATE content_zombies56.cpp')) {
    $config+="`ntarget_sources(pvztyped72 PRIVATE content_zombies56.cpp content_zombies70.cpp september_zombies.cpp native_barrels.cpp content_zombie_bindings.cpp)`n"
}
if(-not $config.Contains('add_executable(content_controllers72_probe')) {
    $config+=@'

add_executable(content_controllers72_probe "CONTENT_STAGE/content_controllers_probe.cpp")
target_link_libraries(content_controllers72_probe PRIVATE pvztyped72)
target_include_directories(content_controllers72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
'@.Replace('CONTENT_STAGE',$stage.Replace('\','/'))
}
[IO.File]::WriteAllText($configPath,$config,[Text.UTF8Encoding]::new($false))
$pinned=[ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $stage 'source') -Recurse -File | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
Get-ChildItem -LiteralPath $stage -File -Filter '*.cpp' | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$pinned | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'controller-build-inputs.json') -Encoding UTF8
& $cmake -S $typed -B (Join-Path $stage 'build') -G 'Visual Studio 17 2022' -A x64 *> (Join-Path $stage 'controller-configure.log')
if($LASTEXITCODE -ne 0){throw "CMake configure failed: $LASTEXITCODE"}
& $cmake --build (Join-Path $stage 'build') --config Release --target content_zombies72_probe content_controllers72_probe --parallel 1 *> (Join-Path $stage 'controller-build.log')
exit $LASTEXITCODE
