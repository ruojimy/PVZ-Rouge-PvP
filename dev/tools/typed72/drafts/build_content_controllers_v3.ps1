$ErrorActionPreference='Stop'
$workspace='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$previous=Join-Path $workspace 'build/typed72-content-controller-v2'
$bonus=Join-Path $workspace 'build/typed72-bonus-v2'
$stage=Join-Path $workspace 'build/typed72-content-controller-v3'
$typed=Join-Path $stage 'source/src/sim/typed'
$draft=Join-Path $workspace 'tools/typed72/drafts'
$cmake='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
if(Test-Path -LiteralPath $stage){throw 'v3 stage exists; inspect before reuse.'}
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $previous 'source') -Destination $stage -Recurse
Get-ChildItem -LiteralPath $previous -File -Filter '*.cpp' | Copy-Item -Destination $stage
$files=@('native_status.h','native_status.cpp','native_status_state.h','native_tick.h','native_tick.cpp',
    'hero.h','hero.cpp','combat_events.h','sourced_context.cpp',
    'content_zombies.h','content_zombies.cpp','content_zombie_state.h','cart_lifecycle.h','cart_lifecycle.cpp',
    'content_zombie56_state.h','content_zombies56.h','content_zombies56.cpp',
    'content_zombie70_state.h','content_zombies70.h','content_zombies70.cpp',
    'september_zombies.h','september_zombies.cpp','native_barrels.h','native_barrels.cpp',
    'content_zombie_bindings.h','content_zombie_bindings.cpp',
    'content_combat_state.h','content_entity_state.h','barrel_projectiles.h','barrel_projectiles.cpp',
    'bonus_state.h','bonus_projectiles.h','bonus_projectiles.cpp')
foreach($name in $files){Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $typed $name)}
foreach($name in @('state.h','plant.h')){Copy-Item -LiteralPath (Join-Path $bonus "source/src/sim/typed/$name") -Destination (Join-Path $typed $name)}
foreach($name in @('native_status_probe.cpp','native_tick_probe.cpp','content_zombies_probe.cpp','content_controllers_probe.cpp')){
    Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $stage $name)
}
$statePath=Join-Path $typed 'state.h'
$state=[IO.File]::ReadAllText($statePath).Replace('#include "sim/typed/bonus_state.h"',"#include `"sim/typed/bonus_state.h`"`n#include `"sim/typed/content_entity_state.h`"")
$state=$state.Replace('BonusEntityState bonus;',"BonusEntityState bonus;`n    ContentEntityState content_state;")
[IO.File]::WriteAllText($statePath,$state,[Text.UTF8Encoding]::new($false))
$configPath=Join-Path $typed 'CMakeLists.txt'
$config=[IO.File]::ReadAllText($configPath).Replace($previous.Replace('\','/'),$stage.Replace('\','/'))
$config+="`ntarget_sources(pvztyped72 PRIVATE bonus_projectiles.cpp barrel_projectiles.cpp)`n"
[IO.File]::WriteAllText($configPath,$config,[Text.UTF8Encoding]::new($false))
$pinned=[ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $stage 'source') -Recurse -File | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
Get-ChildItem -LiteralPath $stage -File -Filter '*.cpp' | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$pinned | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'controller-build-inputs.json') -Encoding UTF8
& $cmake -S $typed -B (Join-Path $stage 'build') -G 'Visual Studio 17 2022' -A x64 *> (Join-Path $stage 'controller-configure.log')
if($LASTEXITCODE -ne 0){throw "CMake configure failed: $LASTEXITCODE"}
& $cmake --build (Join-Path $stage 'build') --config Release --target content_zombies72_probe content_controllers72_probe --parallel 1 *> (Join-Path $stage 'controller-build.log')
exit $LASTEXITCODE
