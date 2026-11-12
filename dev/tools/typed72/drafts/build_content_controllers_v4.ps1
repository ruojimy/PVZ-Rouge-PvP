$ErrorActionPreference='Stop'
$workspace='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$previous=Join-Path $workspace 'build/typed72-content-controller-v3'
$stage=Join-Path $workspace 'build/typed72-content-controller-v4'
$typed=Join-Path $stage 'source/src/sim/typed'
$draft=Join-Path $workspace 'tools/typed72/drafts'
$cmake='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
if(Test-Path -LiteralPath $stage){throw 'v4 stage exists; inspect before reuse.'}
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $previous 'source') -Destination $stage -Recurse
Get-ChildItem -LiteralPath $previous -File -Filter '*.cpp' | Copy-Item -Destination $stage
$files=@('native_status.h','native_status.cpp','native_status_state.h','native_tick.h','native_tick.cpp',
    'hero.h','hero.cpp','combat_events.h','sourced_context.cpp','bonus_state.h',
    'bonus_projectiles.h','bonus_projectiles.cpp','bonus_plants.h','bonus_plants.cpp','bonus_scan.h','bonus_scan.cpp',
    'content_zombies.h','content_zombies.cpp','content_zombie_state.h','cart_lifecycle.h','cart_lifecycle.cpp',
    'content_zombie56_state.h','content_zombies56.h','content_zombies56.cpp',
    'content_zombie70_state.h','content_zombies70.h','content_zombies70.cpp',
    'september_zombies.h','september_zombies.cpp','native_barrels.h','native_barrels.cpp',
    'content_zombie_bindings.h','content_zombie_bindings.cpp','zombie_actions.h','barrel_crush.h','barrel_crush.cpp',
    'content_combat_state.h','content_entity_state.h','barrel_projectiles.h','barrel_projectiles.cpp',
    'content_darts.h','content_darts.cpp','content_damage.h','content_damage.cpp','content_frost.h','content_frost.cpp',
    'content_plant70_state.h','content_plants70.h','content_plants70.cpp',
    'content_plant_state.h','content_vines.h','content_vines.cpp','content_lantern.h','content_lantern.cpp',
    'native_content_phase.h','native_content_phase.cpp')
foreach($name in $files){Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $typed $name)}
& (Join-Path $draft 'overlay_content_source.ps1') -TypedDirectory $typed
foreach($name in @('native_status_probe.cpp','native_tick_probe.cpp','content_zombies_probe.cpp','content_controllers_probe.cpp')){
    Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $stage $name)
}
$configPath=Join-Path $typed 'CMakeLists.txt'
$config=[IO.File]::ReadAllText($configPath).Replace($previous.Replace('\','/'),$stage.Replace('\','/'))
$config+="`ntarget_sources(pvztyped72 PRIVATE bonus_plants.cpp bonus_scan.cpp content_darts.cpp content_damage.cpp content_frost.cpp content_plants70.cpp content_vines.cpp content_lantern.cpp native_content_phase.cpp)`n"
[IO.File]::WriteAllText($configPath,$config,[Text.UTF8Encoding]::new($false))
$pinned=[ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $stage 'source') -Recurse -File | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
Get-ChildItem -LiteralPath $stage -File -Filter '*.cpp' | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$pinned | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'controller-build-inputs.json') -Encoding UTF8
& $cmake -S $typed -B (Join-Path $stage 'build') -G 'Visual Studio 17 2022' -A x64 *> (Join-Path $stage 'controller-configure.log')
if($LASTEXITCODE -ne 0){throw "CMake configure failed: $LASTEXITCODE"}
& $cmake --build (Join-Path $stage 'build') --config Release --target content_controllers72_probe --parallel 1 *> (Join-Path $stage 'controller-build.log')
exit $LASTEXITCODE
