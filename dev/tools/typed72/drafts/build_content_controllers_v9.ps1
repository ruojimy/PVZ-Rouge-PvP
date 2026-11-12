$ErrorActionPreference='Stop'
$workspace='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
$previous=Join-Path $workspace 'build/typed72-content-controller-v8'
$stage=Join-Path $workspace 'build/typed72-content-controller-v9'
$cmake='C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
if(Test-Path -LiteralPath $stage){throw 'v9 stage exists'}
New-Item -ItemType Directory -Path $stage | Out-Null
Get-ChildItem -LiteralPath $previous -File -Filter '*.cpp' | Copy-Item -Destination $stage
Copy-Item -LiteralPath (Join-Path $workspace 'tools/typed72/drafts/content_phase_probe.cpp') -Destination (Join-Path $stage 'content_phase_probe.cpp')
$config=@'
cmake_minimum_required(VERSION 3.20)
project(ContentProbeRevision LANGUAGES CXX)
add_library(content_v8 STATIC IMPORTED)
set_target_properties(content_v8 PROPERTIES IMPORTED_LOCATION "@PREVIOUS@/build/Release/pvztyped72.lib")
add_executable(content_phase72_probe content_phase_probe.cpp)
target_compile_features(content_phase72_probe PRIVATE cxx_std_20)
target_compile_options(content_phase72_probe PRIVATE /utf-8 /fp:precise /W4 /MP1 /FS)
target_include_directories(content_phase72_probe PRIVATE "@PREVIOUS@/source/src" "@ROOT@/src" "@ROOT@/third_party" "@ROOT@/tools/typed72")
target_link_libraries(content_phase72_probe PRIVATE content_v8)
'@
$config=$config.Replace('@PREVIOUS@',$previous.Replace('\','/')).Replace('@ROOT@',$workspace.Replace('\','/'))
[IO.File]::WriteAllText((Join-Path $stage 'CMakeLists.txt'),$config,[Text.UTF8Encoding]::new($false))
$pins=Get-Content -LiteralPath (Join-Path $previous 'controller-build-inputs.json') -Raw | ConvertFrom-Json -AsHashtable
Get-ChildItem -LiteralPath $stage -File | ForEach-Object {$pins[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$library=Join-Path $previous 'build/Release/pvztyped72.lib'
$pins[$library]=(Get-FileHash -LiteralPath $library -Algorithm SHA256).Hash.ToLowerInvariant()
$pins | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'controller-build-inputs.json') -Encoding UTF8
& $cmake -S $stage -B (Join-Path $stage 'build') -G 'Visual Studio 17 2022' -A x64 *> (Join-Path $stage 'controller-configure.log')
if($LASTEXITCODE -ne 0){throw 'v9 configure failed'}
& $cmake --build (Join-Path $stage 'build') --config Release --target content_phase72_probe --parallel 1 *> (Join-Path $stage 'controller-build.log')
exit $LASTEXITCODE
