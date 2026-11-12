$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$stage=Join-Path $taskRoot 'build/typed72-room-stage'
$source=Join-Path $stage 'source'
$clock=Join-Path $taskRoot 'build/typed72-native-clock-v2'
function Copy-Changed([string]$From,[string]$To){
    if(!(Test-Path -LiteralPath $To) -or (Get-FileHash -LiteralPath $From).Hash -ne (Get-FileHash -LiteralPath $To).Hash){
        New-Item -ItemType Directory -Path (Split-Path -Parent $To) -Force | Out-Null
        Copy-Item -LiteralPath $From -Destination $To -Force
    }
}
foreach($part in @('src','tools/typed72','third_party')){
    $base=Join-Path (Join-Path $clock 'source') $part
    if(!(Test-Path -LiteralPath $base)){continue}
    foreach($file in Get-ChildItem -LiteralPath $base -Recurse -File){
        if($file.Name -eq 'CMakeLists.txt'){continue}
        $relative=$file.FullName.Substring($base.Length).TrimStart('\','/')
        Copy-Changed $file.FullName (Join-Path (Join-Path $source $part) $relative)
    }
}
foreach($name in @('native_tick_probe.cpp','native_status_probe.cpp','native_clock_probe.cpp')){
    Copy-Changed (Join-Path $clock $name) (Join-Path $source "tools/typed72/$name")
}
foreach($name in @('attack_source.h','borrowed_zombie_kind.h')){
    Copy-Changed (Join-Path $taskRoot "src/sim/typed/$name") (Join-Path $source "src/sim/typed/$name")
}
foreach($name in @('attack_identity.h','attack_identity.cpp')){
    Copy-Changed (Join-Path $PSScriptRoot $name) (Join-Path $source "src/sim/typed/$name")
}
foreach($file in Get-ChildItem -LiteralPath $PSScriptRoot -File){
    if($file.Name -notmatch '^(room|command|ai|replay)_'){continue}
    if($file.Name -match '(_probe\.cpp|_fixture\.inc)$'){$dest=Join-Path $source "tools/typed72/$($file.Name)"}
    elseif($file.Extension -in @('.cpp','.h')){$dest=Join-Path $source "src/sim/typed/$($file.Name)"}
    else{continue}
    Copy-Changed $file.FullName $dest
}
$cmake=Join-Path $source 'src/sim/typed/CMakeLists.txt'
$text=[IO.File]::ReadAllText($cmake)
$text=[regex]::Replace($text,'(?s)\r?\n# BEGIN ROOM BOUNDARIES.*?# END ROOM BOUNDARIES\r?\n?',"`n")
$text+=@'

# BEGIN ROOM BOUNDARIES
target_sources(pvztyped72 PRIVATE ai_controls.cpp ai_field.cpp ai_observation.cpp ai_observation_builder.cpp ai_observation_codec.cpp ai_plan_codec.cpp ai_team_support.cpp room_wire.cpp replay_codec.cpp replay_digest.cpp replay_driver.cpp replay_recording.cpp)
add_executable(room_boundary72_probe "${PVZ_TYPED_ROOT}/tools/typed72/room_boundary_probe.cpp")
target_link_libraries(room_boundary72_probe PRIVATE pvztyped72)
target_include_directories(room_boundary72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
add_executable(ai_observation72_probe "${PVZ_TYPED_ROOT}/tools/typed72/ai_observation_probe.cpp")
target_link_libraries(ai_observation72_probe PRIVATE pvztyped72)
target_include_directories(ai_observation72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
target_sources(pvztyped72 PRIVATE room_transport_queue.cpp room_transport.cpp)
if(WIN32)
  target_link_libraries(pvztyped72 PUBLIC ws2_32)
else()
  find_package(Threads REQUIRED)
  target_link_libraries(pvztyped72 PUBLIC Threads::Threads)
endif()
add_executable(room_transport72_probe "${PVZ_TYPED_ROOT}/tools/typed72/room_transport_probe.cpp")
target_link_libraries(room_transport72_probe PRIVATE pvztyped72)
target_include_directories(room_transport72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
target_sources(pvztyped72 PRIVATE ai_tactical_base.cpp ai_human_prior.cpp ai_firing.cpp ai_plant_placement.cpp room_public.cpp room_public_codec.cpp room_public_terrain.cpp room_native_pose.cpp room_native_pose_codec.cpp room_match_control.cpp)
add_executable(ai_tactical72_probe "${PVZ_TYPED_ROOT}/tools/typed72/ai_tactical_probe.cpp")
target_link_libraries(ai_tactical72_probe PRIVATE pvztyped72)
target_include_directories(ai_tactical72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
add_executable(room_public72_probe "${PVZ_TYPED_ROOT}/tools/typed72/room_public_probe.cpp")
target_link_libraries(room_public72_probe PRIVATE pvztyped72)
target_include_directories(room_public72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
add_executable(ai_firing72_probe "${PVZ_TYPED_ROOT}/tools/typed72/ai_firing_probe.cpp")
target_link_libraries(ai_firing72_probe PRIVATE pvztyped72)
target_include_directories(ai_firing72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
add_executable(replay_journal72_probe "${PVZ_TYPED_ROOT}/tools/typed72/replay_journal_probe.cpp")
target_link_libraries(replay_journal72_probe PRIVATE pvztyped72)
target_include_directories(replay_journal72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
add_executable(replay_lifecycle72_probe "${PVZ_TYPED_ROOT}/tools/typed72/replay_lifecycle_probe.cpp")
target_link_libraries(replay_lifecycle72_probe PRIVATE pvztyped72)
target_include_directories(replay_lifecycle72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
add_executable(room_match72_probe "${PVZ_TYPED_ROOT}/tools/typed72/room_match_probe.cpp")
target_link_libraries(room_match72_probe PRIVATE pvztyped72)
target_include_directories(room_match72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
add_executable(ai_plant_placement72_probe "${PVZ_TYPED_ROOT}/tools/typed72/ai_plant_placement_probe.cpp")
target_link_libraries(ai_plant_placement72_probe PRIVATE pvztyped72)
target_include_directories(ai_plant_placement72_probe PRIVATE "${PVZ_TYPED_ROOT}/third_party" "${PVZ_TYPED_ROOT}/tools/typed72")
# END ROOM BOUNDARIES
'@
[IO.File]::WriteAllText($cmake,$text,[Text.UTF8Encoding]::new($false))
$pins=[ordered]@{}
foreach($file in Get-ChildItem -LiteralPath $source -File -Recurse | Sort-Object FullName){$pins[$file.FullName]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$pins|ConvertTo-Json -Depth 3|Set-Content -LiteralPath (Join-Path $stage 'build-inputs.json') -Encoding utf8
Write-Output $stage
