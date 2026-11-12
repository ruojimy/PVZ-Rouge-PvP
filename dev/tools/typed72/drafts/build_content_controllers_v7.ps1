$ErrorActionPreference='Stop'
$workspace='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$previous=Join-Path $workspace 'build/typed72-content-controller-v6'
$stage=Join-Path $workspace 'build/typed72-content-controller-v7'
$typed=Join-Path $stage 'source/src/sim/typed'
$draft=Join-Path $workspace 'tools/typed72/drafts'
$cmake='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
if(Test-Path -LiteralPath $stage){throw 'v7 stage exists; inspect before reuse.'}
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $previous 'source') -Destination $stage -Recurse
Get-ChildItem -LiteralPath $previous -File -Filter '*.cpp' | Copy-Item -Destination $stage
foreach($name in @('content_damage.h','content_damage.cpp','zombie_actions.h','zombie_actions.cpp','native_content_phase.h','native_content_phase.cpp')){
    Copy-Item -LiteralPath (Join-Path $draft $name) -Destination (Join-Path $typed $name)
}
& (Join-Path $draft 'overlay_content_source.ps1') -TypedDirectory $typed
Copy-Item -LiteralPath (Join-Path $draft 'content_phase_probe.cpp') -Destination (Join-Path $stage 'content_phase_probe.cpp')
$configPath=Join-Path $typed 'CMakeLists.txt'
$config=[IO.File]::ReadAllText($configPath).Replace($previous.Replace('\','/'),$stage.Replace('\','/'))
[IO.File]::WriteAllText($configPath,$config,[Text.UTF8Encoding]::new($false))
$pinned=[ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $stage 'source') -Recurse -File | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
Get-ChildItem -LiteralPath $stage -File -Filter '*.cpp' | ForEach-Object {$pinned[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$pinned | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'controller-build-inputs.json') -Encoding UTF8
& $cmake -S $typed -B (Join-Path $stage 'build') -G 'Visual Studio 17 2022' -A x64 *> (Join-Path $stage 'controller-configure.log')
if($LASTEXITCODE -ne 0){throw "CMake configure failed: $LASTEXITCODE"}
& $cmake --build (Join-Path $stage 'build') --config Release --target content_controllers72_probe content_phase72_probe --parallel 1 *> (Join-Path $stage 'controller-build.log')
exit $LASTEXITCODE
