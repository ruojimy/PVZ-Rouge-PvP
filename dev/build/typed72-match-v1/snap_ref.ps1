param([string]$Name,[string]$Out)
$root='C:\Users\xiech\Downloads\PVZ_rougePvP_native'
Set-Location -LiteralPath $root
$env:SDL_VIDEODRIVER='dummy';$env:SDL_AUDIODRIVER='dummy';$env:PYTHONIOENCODING='utf-8'
New-Item -ItemType Directory -Force $Out | Out-Null
$src="tools\scenarios\_expanded_$Name.json";if(-not(Test-Path $src)){$src="tools\scenarios\$Name.json"};if(Test-Path "build\typed72-match-v1\scenarios\$Name.json"){$src="build\typed72-match-v1\scenarios\$Name.json"}
$env:PVP_USERDATA="$Out\ud_snap_$Name";$env:REF_SNAPSHOTS="$Out\$Name.snap.jsonl"
& build\typed72-ref-recorder-v4\build\Release\ref72_record.exe $src "$Out\$Name.snapref.jsonl" *> "$Out\$Name.snapref.log"
"v snapshot exit=$LASTEXITCODE"
Remove-Item Env:REF_SNAPSHOTS
