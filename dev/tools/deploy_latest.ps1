param([Parameter(Mandatory=$true)][string]$ReleaseDirectory)
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$releaseRoot=[IO.Path]::GetFullPath($ReleaseDirectory)
$distRoot=[IO.Path]::GetFullPath((Join-Path $projectRoot 'dist'))+[IO.Path]::DirectorySeparatorChar
if(-not $releaseRoot.StartsWith($distRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Release must be inside this project dist directory'}
$manifest=Join-Path $releaseRoot 'SHA256SUMS'
if(-not (Test-Path -LiteralPath $manifest -PathType Leaf)){throw 'Release manifest missing'}
$targetRoot=Join-Path $projectRoot 'PVZ_rougePvP_native'
$savePath=Join-Path $targetRoot 'pvp_userdata'
$saveBefore=if(Test-Path -LiteralPath (Join-Path $savePath 'player.json')){(Get-FileHash -LiteralPath (Join-Path $savePath 'player.json') -Algorithm SHA256).Hash}else{$null}
foreach($line in Get-Content -LiteralPath $manifest -Encoding utf8){
    if($line -notmatch '^([a-fA-F0-9]{64})\s+\*?\./(.+)$'){throw "Invalid release manifest line: $line"}
    $relativeName=$Matches[2]
    $sourceFile=[IO.Path]::GetFullPath((Join-Path $releaseRoot $relativeName))
    $targetFile=[IO.Path]::GetFullPath((Join-Path $targetRoot $relativeName))
    if(-not $sourceFile.StartsWith($releaseRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or -not $targetFile.StartsWith($targetRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe manifest path'}
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($targetFile)) -Force | Out-Null
    Copy-Item -LiteralPath $sourceFile -Destination $targetFile -Force
}
Copy-Item -LiteralPath $manifest -Destination (Join-Path $targetRoot 'SHA256SUMS') -Force
$sourceHash=(Get-FileHash -LiteralPath (Join-Path $releaseRoot 'PvZPvPNative.exe') -Algorithm SHA256).Hash
$targetHash=(Get-FileHash -LiteralPath (Join-Path $targetRoot 'PvZPvPNative.exe') -Algorithm SHA256).Hash
if($sourceHash -ne $targetHash){throw 'Launcher target EXE differs from release'}
$saveAfter=if(Test-Path -LiteralPath (Join-Path $savePath 'player.json')){(Get-FileHash -LiteralPath (Join-Path $savePath 'player.json') -Algorithm SHA256).Hash}else{$null}
if($saveBefore -ne $saveAfter){throw 'Player save changed during deployment'}
$record=[ordered]@{release=$releaseRoot;launcher=(Join-Path $projectRoot '启动PvP.cmd');target=(Join-Path $targetRoot 'PvZPvPNative.exe');exe_sha256=$targetHash.ToLower();userdata=$savePath;player_save_sha256=$saveAfter;player_save_preserved=$true}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'dist\latest-native-release.json') -Encoding utf8
$record | ConvertTo-Json
